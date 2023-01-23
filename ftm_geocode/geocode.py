import os
from datetime import datetime
from typing import Any, Generator, TypedDict

import geopy.geocoders
import orjson
from banal import clean_dict
from followthemoney import model
from followthemoney.proxy import E
from geopy.adapters import AdapterHTTPError
from geopy.exc import GeocoderQueryError, GeocoderServiceError
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import get_geocoder_for_service

from . import settings
from .cache import get_cache
from .io import Formats
from .logging import get_logger
from .model import Address, GeocodingResult, get_address_id, get_canonical_id
from .settings import GEOCODERS
from .util import (
    apply_address,
    get_country_name,
    get_proxy_addresses,
    normalize,
    normalize_google,
)

geopy.geocoders.options.default_user_agent = settings.USER_AGENT
geopy.geocoders.options.default_timeout = settings.DEFAULT_TIMEOUT

log = get_logger(__name__)


class GeocodingContext(TypedDict):
    country: str | None = None


class Geocoder:
    SETTINGS = {
        GEOCODERS.nominatim: {
            "config": {
                "domain": os.environ.get("FTMGEO_NOMINATIM_DOMAIN"),
            },
            "params": lambda **ctx: {"country_codes": ctx.get("country")},
        },
        GEOCODERS.googlev3: {
            "config": {
                "api_key": os.environ.get("FTMGEO_GOOGLE_API_KEY"),
            },
            "params": lambda **ctx: {"region": ctx.get("country")},
            "query": lambda query, **ctx: normalize_google(query),
        },
        GEOCODERS.arcgis: {
            "params": lambda **ctx: {"out_fields": "*"},
            "query": lambda query, **ctx: ", ".join(
                (query, get_country_name(ctx.get("country")) or "")
            ),
        },
    }

    def __init__(self, geocoder: GEOCODERS):
        self._settings = self.SETTINGS.get(geocoder, {})
        config = clean_dict(self._settings.get("config", {}))
        self.geocoder = get_geocoder_for_service(geocoder.value)(**config)

    def get_params(self, **ctx: GeocodingContext) -> dict[str, Any]:
        func = self._settings.get("params", lambda **ctx: {})
        return clean_dict(func(**ctx))

    def get_query(self, query: str, **ctx: GeocodingContext) -> str:
        func = self._settings.get("query", lambda query, **ctx: normalize(query))
        return func(query, **ctx)


def _geocode(
    geocoder: GEOCODERS, value: str, **ctx: GeocodingContext
) -> GeocodingResult | None:
    geolocator = Geocoder(geocoder)
    value = geolocator.get_query(value, **ctx)
    geocoding_params = geolocator.get_params(**ctx)
    geocode = RateLimiter(
        geolocator.geocoder.geocode,
        min_delay_seconds=settings.MIN_DELAY_SECONDS,
        max_retries=settings.MAX_RETRIES,
    )
    address_id = get_address_id(value, **ctx)
    cache = get_cache()

    try:
        result = geocode(value, **geocoding_params)
    except (AdapterHTTPError, GeocoderQueryError, GeocoderServiceError) as e:
        result = None
        log.error(
            f"{e}: {e.message} `{value}`",
            geocoder=geocoder.value,
            **geocoding_params,
        )

    if result is not None:
        log.info(
            f"Geocoder hit: `{value}`",
            geocoder=geocoder.value,
            **geocoding_params,
        )
        address = Address.from_string(result.address, **ctx)
        geocoder_place_id = result.raw.get("place_id")
        if geocoder_place_id:
            canonical_id = get_canonical_id(geocoder, geocoder_place_id)
        else:
            canonical_id = address.get_id()
        result = GeocodingResult(
            address_id=address_id,
            canonical_id=canonical_id,
            original_line=value,
            result_line=result.address,
            country=address.get_country(),
            lat=result.latitude,
            lon=result.longitude,
            geocoder=geocoder.value,
            geocoder_place_id=geocoder_place_id,
            geocoder_raw=orjson.dumps(result.raw),
            ts=datetime.now(),
        )
        cache.put(result)
        return result


def geocode_line(
    geocoder: list[GEOCODERS],
    value: str,
    use_cache: bool | None = True,
    apply_nuts: bool | None = False,
    verbose_log: bool | None = False,
    **ctx: GeocodingContext,
) -> GeocodingResult | None:

    # look in cache
    if use_cache:
        cache = get_cache()
        result = cache.get(value, **ctx)
        if result is not None:
            if verbose_log:
                log.info(f"Cache hit: `{value}`", cache=str(cache), **ctx)
            if apply_nuts:
                result.apply_nuts()
            return result

    # geocode
    geocoders = geocoder
    for geocoder in geocoders:
        result = _geocode(geocoder, value, **ctx)
        if result is not None:
            if apply_nuts:
                result.apply_nuts()
            return result

    log.warning(f"Not found: `{value}`", geocoder=geocoder)


def geocode_proxy(
    geocoder: list[GEOCODERS],
    proxy: E | dict[str, Any],
    use_cache: bool | None = True,
    apply_nuts: bool | None = False,
    verbose_log: bool | None = False,
    output_format: Formats | None = Formats.ftm,
    rewrite_ids: bool | None = True,
) -> Generator[E | GeocodingResult, None, None]:
    proxy = model.get_proxy(proxy)
    if not proxy.schema.is_a("Thing"):
        if output_format == Formats.ftm:
            yield proxy
        return

    is_address = proxy.schema.is_a("Address")
    ctx = {"country": proxy.first("country") or ""}
    results = (
        geocode_line(
            geocoder,
            value,
            use_cache=use_cache,
            apply_nuts=apply_nuts,
            verbose_log=verbose_log,
            **ctx,
        )
        for value in get_proxy_addresses(proxy)
    )
    if output_format == Formats.ftm:
        for result in results:
            if result is not None:
                address = Address.from_result(result)
                address = address.to_proxy()
                proxy = apply_address(proxy, address, rewrite_id=rewrite_ids)
                if is_address:
                    yield proxy
                else:
                    yield address
        if not is_address:
            yield proxy
    else:
        for result in results:
            if result is not None:
                yield result
