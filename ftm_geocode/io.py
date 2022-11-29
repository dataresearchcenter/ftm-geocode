import csv
from enum import Enum
from typing import Generator, Literal

import orjson
import typer
from followthemoney import model
from followthemoney.proxy import EntityProxy

from .model import Address, GeocodingResult


class Formats(Enum):
    csv = "csv"
    ftm = "ftm"


Row = tuple[str, str | None, str | None, ...]


def dump_proxy(proxy: EntityProxy) -> str:
    return orjson.dumps(proxy.to_dict(), option=orjson.OPT_APPEND_NEWLINE).decode()


def read_ftm(input_file: typer.FileText) -> Generator[Row, None, None]:
    for row in input_file.readlines():
        yield model.get_proxy(orjson.loads(row))


def write_ftm(output_file: typer.FileTextWrite):
    def _write(data: GeocodingResult | EntityProxy):
        if isinstance(data, GeocodingResult):
            address = Address.from_result(data)
            proxy = address.to_proxy()
            output_file.write(dump_proxy(proxy))
        else:
            output_file.write(dump_proxy(data))

    return _write


def read_csv(
    input_file: typer.FileText, header: bool = True
) -> Generator[Row, None, None]:
    reader = csv.reader(input_file)
    if header:
        next(reader)
    for row in reader:
        address, *rest = row
        country, language = None, None
        if len(rest):
            country, *rest = rest
            if len(rest):
                language, *rest = rest
            else:
                language = country
        yield address, country, language, *rest


def write_csv(
    output_file: typer.FileTextWrite,
    include_raw: bool | None = False,
    extra_fields: list[str] | None = [],
):
    fieldnames = GeocodingResult.__annotations__.keys()
    if not include_raw:
        fieldnames = [
            f for f in fieldnames if f not in ("ts", "geocoder_raw", "cache_key")
        ]
    fieldnames = set(fieldnames) | set(extra_fields)

    writer = csv.DictWriter(output_file, fieldnames=fieldnames)
    writer.writeheader()

    def _write(
        result: GeocodingResult | None = None, extra_data: dict[str, str] | None = {}
    ):
        if result is not None:
            data = {**extra_data, **result.dict()}
        else:
            data = extra_data
        data = {k: v for k, v in data.items() if k in fieldnames}
        writer.writerow(data)

    return _write


def get_reader(
    input_file: typer.FileText, input_format: Formats, **kwargs
) -> Literal[read_ftm, read_csv]:
    if input_format == Formats.ftm:
        return read_ftm(input_file)
    if input_format == Formats.csv:
        return read_csv(input_file, **kwargs)


def get_writer(
    output_file: typer.FileTextWrite, output_format: Formats, **kwargs
) -> Literal[write_ftm, write_csv]:
    if output_format == Formats.ftm:
        return write_ftm(output_file)
    if output_format == Formats.csv:
        return write_csv(output_file, **kwargs)
