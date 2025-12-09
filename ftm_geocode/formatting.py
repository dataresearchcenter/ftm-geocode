"""
Address formatting module - standalone.

Formats address components into normalized address strings.
"""

from followthemoney.util import join_text
from ftmq.util import get_country_code
from normality import squash_spaces
from rigour.addresses import format_address_line

from ftm_geocode.parsing import ParsedAddress
from ftm_geocode.util import get_first


def format_address(
    parsed: ParsedAddress,
    country: str | None = None,
) -> str:
    """
    Format parsed address components into a normalized address line.

    Uses rigour's format_address_line for country-specific formatting.

    Args:
        parsed: ParsedAddress with components
        country: Override country for formatting rules

    Returns:
        Formatted address string
    """
    country_code = get_country_code(country or parsed.country_code or parsed.country)

    data = {
        "attention": parsed.near,
        "house": join_text(parsed.house, parsed.po_box),
        "house_number": parsed.house_number,
        "road": parsed.road,
        "postcode": parsed.postcode,
        "city": parsed.city,
        "state": parsed.state,
        "country": parsed.country,
    }

    return format_address_line(data, country=country_code)


def format_address_from_dict(
    components: dict,
    country: str | None = None,
) -> str:
    """
    Format address components dict into a normalized address line.

    This handles both postal-style keys (road, postcode) and FTM-style keys
    (street, postalCode). Values can be strings or lists (FTM style).

    Args:
        components: Dict with address components (values can be str or list)
        country: Override country for formatting rules

    Returns:
        Formatted address string
    """
    country_code = get_country_code(
        country
        or get_first(components.get("country_code"))
        or get_first(components.get("country"))
    )

    # Handle both postal and FTM key names
    remarks = components.get("remarks", [])
    if isinstance(remarks, list):
        remarks_str = join_text(*remarks)
    else:
        remarks_str = remarks or ""

    attention = squash_spaces(
        join_text(
            get_first(components.get("summary")),
            remarks_str,
            get_first(components.get("near")),
        )
        or ""
    )

    data = {
        "attention": attention or None,
        "house": join_text(
            get_first(components.get("house")),
            get_first(components.get("postOfficeBox")),
            get_first(components.get("po_box")),
        ),
        "house_number": get_first(components.get("house_number")),
        "road": (
            get_first(components.get("road"))
            or get_first(components.get("street"))
            or get_first(components.get("full"))
        ),
        "postcode": get_first(components.get("postcode"))
        or get_first(components.get("postalCode")),
        "city": get_first(components.get("city")),
        "state": get_first(components.get("state")),
    }

    return format_address_line(data, country=country_code)
