import os
from datetime import datetime
from typing import Any, Generator, TypedDict

import geopy.geocoders
from anystore import anycache
from banal import clean_dict
from followthemoney.proxy import EntityProxy
from ftmq.util import ensure_proxy
from geopy.adapters import AdapterHTTPError
from geopy.exc import GeocoderQueryError, GeocoderServiceError
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import get_geocoder_for_service
from normality import collapse_spaces

from ftm_geocode.cache import get_cache, make_cache_key
from ftm_geocode.io import FORMAT_FTM, Formats
from ftm_geocode.logging import get_logger
from ftm_geocode.model import Address, GeocodingResult, get_canonical_id
from ftm_geocode.settings import GEOCODERS, Settings
from ftm_geocode.util import (
    apply_address,
    get_country_name,
    get_proxy_addresses,
    normalize,
    normalize_google,
)

settings = Settings()

geopy.geocoders.options.default_user_agent = settings.user_agent
geopy.geocoders.options.default_timeout = settings.default_timeout

log = get_logger(__name__)


class GeocodingContext(TypedDict):
    country: str | None
    language: str | None


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


@anycache(
    store=get_cache(),
    key_func=lambda _, v, **kwargs: make_cache_key(v, **kwargs),
    model=GeocodingResult,
)
def _geocode(
    geocoder: GEOCODERS,
    value: str,
    use_cache: bool | None = True,
    cache_only: bool | None = False,
    **ctx: GeocodingContext,
) -> GeocodingResult | None:
    if cache_only:
        return
    geolocator = Geocoder(geocoder)
    value = geolocator.get_query(value, **ctx)
    geocoding_params = geolocator.get_params(**ctx)
    geocode = RateLimiter(
        geolocator.geocoder.geocode,
        min_delay_seconds=settings.min_delay_seconds,
        max_retries=settings.max_retries,
    )

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
            address_id = get_canonical_id(geocoder, geocoder_place_id)
        else:
            address_id = address.get_id()
        result = GeocodingResult(
            cache_key=make_cache_key(value, **ctx),
            address_id=address_id,
            original_line=value,
            result_line=result.address,
            country=address.get_country(),
            lat=result.latitude,
            lon=result.longitude,
            geocoder=geocoder.value,
            geocoder_place_id=geocoder_place_id,
            geocoder_raw=result.raw,
            ts=datetime.now(),
        )
        return result


def geocode_line(
    geocoders: list[GEOCODERS],
    value: str,
    use_cache: bool | None = True,
    cache_only: bool | None = False,
    apply_nuts: bool | None = False,
    **ctx: GeocodingContext,
) -> GeocodingResult | None:
    cleaned_value = collapse_spaces(value)
    if cleaned_value:
        for geocoder in geocoders:
            result = _geocode(
                geocoder,
                cleaned_value,
                use_cache=use_cache,
                cache_only=cache_only,
                **ctx,
            )
            if result is not None:
                if apply_nuts:
                    result.apply_nuts()
                return result

    log.warning(f"No geocoding match found: `{value}`", geocoders=geocoders)


def geocode_proxy(
    geocoder: list[GEOCODERS],
    proxy: EntityProxy | dict[str, Any],
    use_cache: bool | None = True,
    cache_only: bool | None = False,
    apply_nuts: bool | None = False,
    output_format: Formats | None = FORMAT_FTM,
    rewrite_ids: bool | None = True,
) -> Generator[EntityProxy | GeocodingResult, None, None]:
    proxy = ensure_proxy(proxy)
    if not proxy.schema.is_a("Thing"):
        if output_format == FORMAT_FTM:
            yield proxy
        return

    is_address = proxy.schema.is_a("Address")
    ctx = {"country": proxy.first("country") or ""}
    results = (
        geocode_line(
            geocoder,
            value,
            use_cache=use_cache,
            cache_only=cache_only,
            apply_nuts=apply_nuts,
            **ctx,
        )
        for value in get_proxy_addresses(proxy)
    )
    if output_format == FORMAT_FTM:
        for result in results:
            if result is not None:
                address = Address.from_result(result)
                address = address.to_proxy()
                address.add("country", ctx["country"])
                address.add("region", result.nuts)
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
