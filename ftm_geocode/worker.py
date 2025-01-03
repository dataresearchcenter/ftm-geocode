from typing import Any

import orjson
from anystore.worker import Worker, WriteWorker
from banal import ensure_list
from nomenklatura.entity import CompositeEntity

from ftm_geocode.cache import get_cache
from ftm_geocode.geocode import geocode_line, geocode_proxy
from ftm_geocode.io import Formats, LatLonRow, PostalRow
from ftm_geocode.model import GeocodingResult, get_address, get_components
from ftm_geocode.nuts import get_nuts, get_proxy_nuts
from ftm_geocode.settings import GEOCODERS, Settings

settings = Settings()


class IOWorker(WriteWorker):
    def __init__(
        self,
        input_format: Formats | None = Formats.ftm,
        output_format: Formats | None = Formats.ftm,
        *args,
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.input_format = input_format
        self.output_format = output_format


class FormatLineWorker(IOWorker):
    def handle_task(self, task: PostalRow) -> None:
        address = get_address(task.original_line, *task.ctx)
        row = task.model_dump()
        row["formatted_line"] = address.get_formatted_line()
        row["country"] = ";".join(address.country)
        self.write(row)


class ParseComponentsWorker(IOWorker):
    def handle_task(self, task: PostalRow) -> None:
        row = get_components(task.original_line, *task.ctx)
        row.update(**task.model_dump())
        self.write(row)


class GeocodeWorker(IOWorker):
    def __init__(
        self,
        use_cache: bool | None = True,
        cache_only: bool | None = False,
        geocoder: list[GEOCODERS] = settings.geocoders,
        rewrite_ids: bool | None = False,
        apply_nuts: bool | None = False,
        *args,
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.use_cache = use_cache
        self.cache_only = cache_only
        self.geocoder = geocoder
        self.rewrite_ids = rewrite_ids
        self.apply_nuts = apply_nuts

    def handle_task(self, task: Any) -> None:
        res = None
        if self.input_format == Formats.ftm:
            res = geocode_proxy(
                self.geocoder,
                task,
                use_cache=self.use_cache,
                cache_only=self.cache_only,
                apply_nuts=self.apply_nuts,
                output_format=self.output_format,
                rewrite_ids=self.rewrite_ids,
            )
        elif self.input_format == Formats.csv:
            res = geocode_line(
                self.geocoder,
                task.original_line,
                use_cache=self.use_cache,
                cache_only=self.cache_only,
                country=task.country,
                apply_nuts=self.apply_nuts,
            )
            if res is not None:
                if self.output_format == Formats.ftm:
                    res = res.to_proxy()
        if res:
            for item in ensure_list(res):
                if item is not None:
                    if self.output_format == Formats.csv:
                        item = item.model_dump(exclude={"geocoder_raw"})
                        item.update(**task.model_dump())
                    elif self.output_format == Formats.ftm:
                        item = orjson.dumps(
                            item.to_dict(), option=orjson.OPT_APPEND_NEWLINE
                        )
                    self.write(item)


class ApplyNutsWorker(IOWorker):
    def handle_task(self, task: Any) -> None:
        res = None
        if self.input_format == Formats.ftm:
            proxy: CompositeEntity = task
            nuts = get_proxy_nuts(proxy)
            if nuts is not None:
                res = nuts.model_dump()
                res["id"] = proxy.id
        elif self.input_format == Formats.csv:
            row: LatLonRow = task
            nuts = get_nuts(row.lon, row.lat)
            if nuts is not None:
                res = nuts.model_dump()
                res.update(**row.model_dump())
        if res:
            self.write(res)


class CachePopulateWorker(Worker):
    def __init__(
        self,
        apply_nuts: bool | None = False,
        ensure_ids: bool | None = False,
        *args,
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.cache = get_cache()
        self.apply_nuts = apply_nuts
        self.ensure_ids = ensure_ids

    def handle_task(self, task: GeocodingResult) -> Any:
        task.apply_cache_key()
        if self.apply_nuts:
            task.apply_nuts()
        if self.ensure_ids:
            task.ensure_canonical_id()
        self.cache.put(task.cache_key, task)
