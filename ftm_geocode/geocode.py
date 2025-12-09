"""
Geocoding module.

Pure geocoding operations - converts address strings to coordinates.
"""

import os
from datetime import datetime
from typing import Any, Generator

import geopy.geocoders
from anystore import anycache
from anystore.logging import get_logger
from banal import clean_dict
from followthemoney import EntityProxy
from ftmq.util import ensure_entity
from geopy.adapters import AdapterHTTPError
from geopy.exc import GeocoderQueryError, GeocoderServiceError
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import get_geocoder_for_service
from normality import squash_spaces

from ftm_geocode.cache import get_cache, make_cache_key
from ftm_geocode.ftm import (
    apply_address,
    get_proxy_addresses,
    make_address_id,
    result_to_proxy,
)
from ftm_geocode.model import GeocodingResult
from ftm_geocode.parsing import normalize_for_cache
from ftm_geocode.settings import GEOCODERS, Settings
from ftm_geocode.util import get_country_name, normalize, normalize_google

settings = Settings()

geopy.geocoders.options.default_user_agent = settings.user_agent
geopy.geocoders.options.default_timeout = settings.default_timeout

log = get_logger(__name__)


class Geocoder:
    """Wrapper for geopy geocoders with service-specific configuration."""

    SETTINGS = {
        GEOCODERS.nominatim: {
            "config": {
                "domain": os.environ.get("FTMGEO_NOMINATIM_DOMAIN"),
            },
            "params": lambda country=None, language=None, **kw: {
                "country_codes": country,
                "language": language,
            },
        },
        GEOCODERS.googlev3: {
            "config": {
                "api_key": os.environ.get("FTMGEO_GOOGLE_API_KEY"),
            },
            "params": lambda country=None, language=None, **kw: {
                "region": country,
                "language": language,
            },
            "query": lambda query, **kw: normalize_google(query),
        },
        GEOCODERS.arcgis: {
            "params": lambda **kw: {"out_fields": "*"},
            "query": lambda query, country=None, **kw: ", ".join(
                (query, get_country_name(country) or "")
            ),
        },
    }

    def __init__(self, geocoder: GEOCODERS):
        self._settings = self.SETTINGS.get(geocoder, {})
        config = clean_dict(self._settings.get("config", {}))
        self.geocoder = get_geocoder_for_service(geocoder.value)(**config)

    def get_params(self, **ctx) -> dict[str, Any]:
        func = self._settings.get("params", lambda **kw: {})
        return clean_dict(func(**ctx))

    def get_query(self, query: str, **ctx) -> str:
        func = self._settings.get("query", lambda query, **kw: normalize(query))
        return func(query, **ctx)


@anycache(
    store=get_cache(),
    key_func=lambda _, v, **kwargs: make_cache_key(v, **kwargs),
    model=GeocodingResult,
)
def _geocode(
    geocoder: GEOCODERS,
    value: str,
    use_cache: bool = True,
    cache_only: bool = False,
    country: str | None = None,
    language: str | None = None,
) -> GeocodingResult | None:
    """
    Internal geocoding function with caching.

    Args:
        geocoder: Which geocoder service to use
        value: Address string to geocode
        use_cache: Whether to use/populate cache
        cache_only: Only return cached results, don't call geocoder
        country: Country hint
        language: Language hint

    Returns:
        GeocodingResult or None if not found
    """
    if cache_only:
        return None

    if len(value) > 255:
        log.warning(f"Geocoding value too long ({len(value)}), skipping", value=value)
        return None

    geolocator = Geocoder(geocoder)
    query = geolocator.get_query(value, country=country, language=language)
    params = geolocator.get_params(country=country, language=language)

    rate_limited_geocode = RateLimiter(
        geolocator.geocoder.geocode,
        min_delay_seconds=settings.min_delay_seconds,
        max_retries=settings.max_retries,
    )

    try:
        result = rate_limited_geocode(query, **params)
    except (AdapterHTTPError, GeocoderQueryError, GeocoderServiceError) as e:
        log.error(
            f"{e}: {e.message} `{value}`",
            geocoder=geocoder.value,
            **params,
        )
        return None

    if result is None:
        return None

    log.info(f"Geocoder hit: `{value}`", geocoder=geocoder.value, **params)

    geocoder_place_id = result.raw.get("place_id")
    address_id = make_address_id(
        result.address,
        country=country,
        osm_id=geocoder_place_id if geocoder == GEOCODERS.nominatim else None,
        google_place_id=geocoder_place_id if geocoder == GEOCODERS.googlev3 else None,
    )

    return GeocodingResult(
        cache_key=normalize_for_cache(value, country=country),
        address_id=address_id,
        original_line=value,
        result_line=result.address,
        country=country or "",
        lat=result.latitude,
        lon=result.longitude,
        geocoder=geocoder.value,
        geocoder_place_id=geocoder_place_id,
        geocoder_raw=result.raw,
        ts=datetime.now(),
    )


def geocode_line(
    geocoders: list[GEOCODERS],
    value: str,
    use_cache: bool = True,
    cache_only: bool = False,
    apply_nuts: bool = False,
    country: str | None = None,
    language: str | None = None,
) -> GeocodingResult | None:
    """
    Geocode an address string using multiple geocoders as fallbacks.

    Args:
        geocoders: List of geocoder services to try (in order)
        value: Address string to geocode
        use_cache: Whether to use/populate cache
        cache_only: Only return cached results
        apply_nuts: Whether to apply EU NUTS codes
        country: Country hint
        language: Language hint

    Returns:
        GeocodingResult or None if no match found
    """
    cleaned_value = squash_spaces(value)
    if not cleaned_value:
        return None

    for geocoder in geocoders:
        result = _geocode(
            geocoder,
            cleaned_value,
            use_cache=use_cache,
            cache_only=cache_only,
            country=country,
            language=language,
        )
        if result is not None:
            if apply_nuts:
                result.apply_nuts()
            return result

    log.warning(f"No geocoding match found: `{value}`", geocoders=geocoders)
    return None


def geocode_proxy(
    geocoders: list[GEOCODERS],
    proxy: EntityProxy | dict[str, Any],
    use_cache: bool = True,
    cache_only: bool = False,
    apply_nuts: bool = False,
    rewrite_ids: bool = True,
) -> Generator[EntityProxy, None, None]:
    """
    Geocode addresses in an FTM entity.

    For Address entities: geocodes and updates the entity.
    For other entities: geocodes address properties and creates linked Address entities.

    Args:
        geocoders: List of geocoder services to try
        proxy: FTM entity to geocode
        use_cache: Whether to use/populate cache
        cache_only: Only return cached results
        apply_nuts: Whether to apply EU NUTS codes
        rewrite_ids: Whether to update Address entity IDs

    Yields:
        EntityProxy objects (addresses and/or the updated original entity)
    """
    from followthemoney import ValueEntity

    proxy = ensure_entity(proxy, ValueEntity)

    if not proxy.schema.is_a("Thing"):
        yield proxy
        return

    is_address = proxy.schema.is_a("Address")
    country = proxy.first("country") or ""

    for address_value in get_proxy_addresses(proxy):
        result = geocode_line(
            geocoders,
            address_value,
            use_cache=use_cache,
            cache_only=cache_only,
            apply_nuts=apply_nuts,
            country=country,
        )
        if result is not None:
            address_proxy = result_to_proxy(result)
            address_proxy.add("country", country)

            proxy = apply_address(proxy, address_proxy, rewrite_id=rewrite_ids)

            if is_address:
                yield proxy
            else:
                yield address_proxy

    if not is_address:
        yield proxy
