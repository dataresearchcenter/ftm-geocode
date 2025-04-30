from ftm_geocode.io import PostalRow
from ftm_geocode.model import get_address, get_components


def format_line(row: PostalRow) -> PostalRow:
    address = get_address(row.original_line, **row.ctx)
    row.formatted_line = address.get_formatted_line()
    return row


def parse_components(row: PostalRow) -> dict[str, str | None]:
    res = get_components(row.original_line, **row.ctx)
    res.update(row.model_dump())
    return res
