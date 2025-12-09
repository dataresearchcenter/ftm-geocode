"""
FollowTheMoney integration module.

Handles conversion between geocoding results and FTM Address entities,
and applying addresses to other entities.
"""

from typing import Generator

from anystore.util import clean_dict
from followthemoney import EntityProxy
from followthemoney.types import registry
from ftmq.util import make_entity

from ftm_geocode.formatting import format_address_from_dict
from ftm_geocode.model import GeocodingResult
from ftm_geocode.parsing import ParsedAddress, normalize_for_cache, parse_address
from ftm_geocode.settings import GEOCODERS

# libpostal fields -> FTM Address properties mapping
# Note: "country" (full name) is not mapped - only "country_code" (ISO code)
# is mapped to FTM's "country" property which expects ISO codes
POSTAL_TO_FTM = {
    "full": "full",
    "house": "remarks",
    "category": "keywords",
    "near": "remarks",
    "house_number": "remarks",
    "road": "street",
    "unit": "remarks",
    "level": "remarks",
    "staircase": "remarks",
    "entrance": "remarks",
    "po_box": "postOfficeBox",
    "postcode": "postalCode",
    "suburb": "remarks",
    "city_district": "remarks",
    "city": "city",
    "island": "region",
    "state_district": "region",
    "state": "state",
    "country_region": "region",
    "country_code": "country",
    "world_region": "region",
}


def make_address_id(
    formatted_line: str,
    country: str | None = None,
    osm_id: str | None = None,
    google_place_id: str | None = None,
) -> str:
    """
    Generate a deterministic Address entity ID.

    Uses place IDs from geocoders when available, otherwise generates
    from normalized address content.
    """
    if osm_id:
        return f"addr-osm-{osm_id}"
    if google_place_id:
        return f"addr-google-{google_place_id}"
    return normalize_for_cache(formatted_line, country=country)


def parsed_to_ftm_properties(parsed: ParsedAddress) -> dict[str, list[str]]:
    """
    Convert ParsedAddress to FTM Address properties.

    Handles the mapping from libpostal field names to FTM property names,
    collecting multiple values into lists.
    """
    props: dict[str, list[str]] = {}

    for postal_key, ftm_key in POSTAL_TO_FTM.items():
        value = getattr(parsed, postal_key, None)
        if value:
            if ftm_key not in props:
                props[ftm_key] = []
            if value not in props[ftm_key]:
                props[ftm_key].append(value)

    return props


def make_address_proxy(
    address_line: str,
    country: str | None = None,
    language: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    osm_id: str | None = None,
    google_place_id: str | None = None,
) -> EntityProxy:
    """
    Create an FTM Address entity from an address string.

    Args:
        address_line: Raw address string
        country: Country hint for parsing
        language: Language hint for parsing
        lat: Latitude (if known)
        lon: Longitude (if known)
        osm_id: OpenStreetMap place ID
        google_place_id: Google Maps place ID

    Returns:
        FTM Address EntityProxy
    """
    parsed = parse_address(address_line, country=country, language=language)
    props = parsed_to_ftm_properties(parsed)

    # Format the address line
    formatted = format_address_from_dict(props, country=country)
    props["full"] = [formatted]

    # Add coordinates if provided
    if lat is not None:
        props["latitude"] = [str(lat)]
    if lon is not None:
        props["longitude"] = [str(lon)]

    # Add place IDs
    if osm_id:
        props["osmId"] = [str(osm_id)]
    if google_place_id:
        props["googlePlaceId"] = [str(google_place_id)]

    # Generate ID
    address_id = make_address_id(
        formatted,
        country=parsed.country_code,
        osm_id=osm_id,
        google_place_id=google_place_id,
    )

    return make_entity(
        {
            "id": address_id,
            "schema": "Address",
            "properties": clean_dict(props),
        }
    )


def result_to_proxy(result: GeocodingResult) -> EntityProxy:
    """
    Convert a GeocodingResult to an FTM Address entity.

    Args:
        result: Geocoding result with coordinates

    Returns:
        FTM Address EntityProxy
    """
    # Determine place IDs based on geocoder
    osm_id = None
    google_place_id = None
    if result.geocoder == GEOCODERS.nominatim.name:
        osm_id = result.geocoder_place_id
    elif result.geocoder == GEOCODERS.google.name:
        google_place_id = result.geocoder_place_id

    proxy = make_address_proxy(
        result.result_line,
        country=result.country,
        lat=result.lat,
        lon=result.lon,
        osm_id=osm_id,
        google_place_id=google_place_id,
    )

    # Add NUTS regions if available
    if result.nuts:
        proxy.add("region", result.nuts)

    return proxy


def get_proxy_addresses(proxy: EntityProxy) -> Generator[str, None, None]:
    """
    Extract address strings from an FTM entity.

    For Address entities, yields the caption.
    For other entities, yields values from address-type properties.
    """
    if proxy.schema.is_a("Address"):
        yield proxy.caption
    else:
        for value in proxy.get_type_values(registry.address):
            yield value


def get_proxy_coords(proxy: EntityProxy) -> tuple[float, float] | None:
    """
    Extract coordinates from an FTM Address entity.

    Returns:
        (longitude, latitude) tuple or None if not available
    """
    try:
        lon = proxy.first("longitude")
        lat = proxy.first("latitude")
        if lon and lat:
            return (float(lon), float(lat))
    except (ValueError, TypeError):
        pass
    return None


def apply_address(
    proxy: EntityProxy,
    address: EntityProxy,
    rewrite_id: bool = True,
) -> EntityProxy:
    """
    Apply an Address entity to another entity.

    For Address entities: merges the address data.
    For other entities: adds addressEntity reference.

    Args:
        proxy: Entity to apply address to
        address: Address entity
        rewrite_id: Whether to update the proxy's ID (for Address entities)

    Returns:
        Updated proxy
    """
    if proxy.schema.is_a("Address"):
        if rewrite_id:
            proxy.id = address.id
        else:
            address.id = proxy.id
        return proxy.merge(address)

    proxy.add("addressEntity", address.id)
    proxy.add("address", address.caption)
    proxy.add("country", address.get("country"))
    return proxy
