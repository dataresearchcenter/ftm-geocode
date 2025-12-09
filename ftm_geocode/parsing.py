"""
Address parsing module - standalone, no FTM dependency.

Parses raw address strings into components using libpostal (if available) or
provides a simple fallback. Also provides normalization for cache key generation.
"""

from collections import defaultdict
from typing import Any

import lazy_import
from followthemoney.util import make_entity_id
from ftmq.util import get_country_code, get_country_name
from pydantic import BaseModel
from rigour.addresses import clean_address, normalize_address

from ftm_geocode.settings import Settings
from ftm_geocode.util import get_first

settings = Settings()
USE_LIBPOSTAL = settings.libpostal


# libpostal parser labels
# https://github.com/openvenues/libpostal#parser-labels
POSTAL_KEYS = [
    "full",
    "house",
    "category",
    "near",
    "house_number",
    "road",
    "unit",
    "level",
    "staircase",
    "entrance",
    "po_box",
    "postcode",
    "suburb",
    "city_district",
    "city",
    "island",
    "state_district",
    "state",
    "country_region",
    "country",
    "country_code",
    "world_region",
]


class ParsedAddress(BaseModel):
    """Parsed address components from libpostal."""

    full: str | None = None
    house: str | None = None
    category: str | None = None
    near: str | None = None
    house_number: str | None = None
    road: str | None = None
    unit: str | None = None
    level: str | None = None
    staircase: str | None = None
    entrance: str | None = None
    po_box: str | None = None
    postcode: str | None = None
    suburb: str | None = None
    city_district: str | None = None
    city: str | None = None
    island: str | None = None
    state_district: str | None = None
    state: str | None = None
    country_region: str | None = None
    country: str | None = None
    country_code: str | None = None
    world_region: str | None = None


def _clean_country_code(value: str | None) -> str | None:
    """Normalize country to ISO code."""
    if value:
        return get_country_code(value)
    return None


def _clean_country_name(value: str | None) -> str | None:
    """Get full country name."""
    if value:
        return get_country_name(value)
    return None


def parse_address(
    value: str,
    country: str | None = None,
    language: str | None = None,
) -> ParsedAddress:
    """
    Parse an address string into components.

    Uses libpostal if available and enabled (FTMGEO_LIBPOSTAL=1),
    otherwise returns just the full address.

    Args:
        value: Raw address string
        country: Country hint (ISO code or name)
        language: Language hint

    Returns:
        ParsedAddress with parsed components
    """
    value = clean_address(value)

    if USE_LIBPOSTAL:
        parse_fn = lazy_import.lazy_callable("postal.parser.parse_address")
        # postal requires non-None values
        ctx = {
            "language": language or "",
            "country": country or "",
        }
        result = parse_fn(value, **ctx)

        # Collect values by key (libpostal can return multiple values per key)
        data: dict[str, set] = defaultdict(set)
        for parsed_value, key in result:
            data[key].add(parsed_value.title())

        # Add country from context if provided
        if country:
            data["country"].add(country)

        # Convert sets to single values
        parsed = ParsedAddress(
            full=value,  # Always preserve original
            house=get_first(data.get("house")),
            category=get_first(data.get("category")),
            near=get_first(data.get("near")),
            house_number=get_first(data.get("house_number")),
            road=get_first(data.get("road")),
            unit=get_first(data.get("unit")),
            level=get_first(data.get("level")),
            staircase=get_first(data.get("staircase")),
            entrance=get_first(data.get("entrance")),
            po_box=get_first(data.get("po_box")),
            postcode=get_first(data.get("postcode")),
            suburb=get_first(data.get("suburb")),
            city_district=get_first(data.get("city_district")),
            city=get_first(data.get("city")),
            island=get_first(data.get("island")),
            state_district=get_first(data.get("state_district")),
            state=get_first(data.get("state")),
            country_region=get_first(data.get("country_region")),
            country=_clean_country_name(get_first(data.get("country"))),
            country_code=_clean_country_code(get_first(data.get("country"))),
            world_region=get_first(data.get("world_region")),
        )
    else:
        # Simple fallback - just return the cleaned address
        parsed = ParsedAddress(
            full=value,
            country=_clean_country_name(country),
            country_code=_clean_country_code(country),
        )

    return parsed


def normalize_for_cache(value: str, country: str | None = None) -> str:
    """
    Normalize an address string for use as a cache key.

    Uses rigour's normalize_address for consistent normalization.

    Args:
        value: Address string
        country: Optional country code

    Returns:
        Normalized cache key string (addr-{country}-{hash})
    """
    normalized = make_entity_id(normalize_address(value, latinize=True, min_length=3))
    if not normalized:
        raise ValueError(f"Invalid address for cache key: {value}")

    country_code = get_country_code(country)
    if country_code:
        return f"addr-{country_code}-{normalized}"
    return f"addr-{normalized}"


def get_components(
    value: str,
    country: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """
    Parse address and return components as a dict.

    Convenience function for CLI output.

    Args:
        value: Address string
        country: Country hint
        language: Language hint

    Returns:
        Dict of non-None parsed components
    """
    parsed = parse_address(value, country=country, language=language)
    return {k: v for k, v in parsed.model_dump().items() if v is not None}
