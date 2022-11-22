import os
from datetime import datetime
from enum import Enum
from typing import Any, Generator, TypedDict

import geopy.geocoders
import orjson
from banal import clean_dict
from followthemoney import model
from followthemoney.proxy import EntityProxy
from geopy.adapters import AdapterHTTPError
from geopy.exc import GeocoderQueryError
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import SERVICE_TO_GEOCODER, get_geocoder_for_service
from normality import collapse_spaces

from . import settings
from .cache import cache
from .io import Formats
from .logging import get_logger
from .model import Address, GeocodingResult, get_address_id
from .util import apply_address, get_proxy_addresses, normalize, normalize_google

geopy.geocoders.options.default_user_agent = settings.USER_AGENT
geopy.geocoders.options.default_timeout = settings.DEFAULT_TIMEOUT

log = get_logger(__name__)

Geocoders = Enum("Geocoders", ((k, k) for k in SERVICE_TO_GEOCODER.keys()))


class GeocodingContext(TypedDict):
    country: str | None = None


CONFIG = {
    Geocoders.nominatim: {
        "domain": os.environ.get("FTMGEO_NOMINATIM_DOMAIN"),
    },
    Geocoders.googlev3: {
        "api_key": os.environ.get("FTMGEO_GOOGLE_API_KEY"),
    },
}

GEOCODER_CTX = {
    Geocoders.nominatim: lambda ctx: {"country_codes": ctx.get("country")},
    Geocoders.googlev3: lambda ctx: {"region": ctx.get("country")},
    Geocoders.arcgis: lambda ctx: {"out_fields": "*"},
}


def get_geocoder(geocoder: Geocoders):
    config = clean_dict(CONFIG.get(geocoder, {}))
    geocoder = get_geocoder_for_service(geocoder.value)
    return geocoder(**config)


def _geocode(
    geocoder: Geocoders, value: str, **ctx: GeocodingContext
) -> GeocodingResult | None:
    value = collapse_spaces(value)
    geocoding_value = normalize(value)
    if "google" in geocoder.value:
        geocoding_value = normalize_google(value)
    geocode_ctx = clean_dict(GEOCODER_CTX.get(geocoder)(ctx))
    geolocator = get_geocoder(geocoder)
    geocode = RateLimiter(
        geolocator.geocode,
        min_delay_seconds=settings.MIN_DELAY_SECONDS,
        max_retries=settings.MAX_RETRIES,
    )
    address_id = get_address_id(value, **ctx)

    try:
        result = geocode(geocoding_value, **geocode_ctx)
    except (AdapterHTTPError, GeocoderQueryError):
        result = None
        pass  # error will be logged

    if result is not None:
        log.info(f"Geocoder hit: `{value}`", geocoder=geocoder.value)
        address = Address.from_string(result.address, **ctx)
        result = GeocodingResult(
            address_id=address_id,
            canonical_id=get_address_id(address),
            original_line=value,
            result_line=result.address,
            country=address.get_country(),
            lat=result.latitude,
            lon=result.longitude,
            geocoder=geocoder.value,
            geocoder_place_id=result.raw.get("place_id"),
            geocoder_raw=orjson.dumps(result.raw),
            ts=datetime.now(),
        )
        cache.put(result)
        return result


def geocode_line(
    geocoder: list[Geocoders],
    value: str,
    use_cache: bool | None = True,
    **ctx: GeocodingContext,
) -> GeocodingResult | None:

    # look in cache
    if use_cache:
        result = cache.get(value, **ctx)
        if result is not None:
            log.info(f"Cache hit: `{value}`", cache=str(cache))
            return result

    # geocode
    geocoders = geocoder
    for geocoder in geocoders:
        result = _geocode(geocoder, value, **ctx)
        if result is not None:
            return result

    log.warning(f"Not found: `{value}`", geocoder=geocoder)


def geocode_proxy(
    geocoder: list[Geocoders],
    proxy: EntityProxy | dict[str, Any],
    use_cache: bool | None = True,
    output_format: Formats | None = Formats.ftm,
) -> Generator[EntityProxy | GeocodingResult, None, None]:
    proxy = model.get_proxy(proxy)
    is_address = proxy.schema.is_a("Address")
    ctx = {"country": proxy.first("country") or ""}
    results = (
        geocode_line(geocoder, value, use_cache=use_cache, **ctx)
        for value in get_proxy_addresses(proxy)
    )
    if output_format == Formats.ftm:
        for result in results:
            if result is not None:
                address = Address.from_result(result)
                address = address.to_proxy()
                proxy = apply_address(proxy, address)
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
