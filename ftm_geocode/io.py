import csv
from enum import StrEnum
from typing import Any, Generator, Iterator, TypeAlias

from anystore.io import SmartHandler, Uri, smart_open
from anystore.util import ensure_uri
from anystore.worker import Writer as _Writer
from ftmq.util import get_country_code
from pydantic import BaseModel, ConfigDict

from ftm_geocode.logging import get_logger
from ftm_geocode.model import GeocodingResult, PostalContext

log = get_logger(__name__)


class Formats(StrEnum):
    csv = "csv"
    ftm = "ftm"


class PostalRow(BaseModel):
    original_line: str
    country: str | None = None
    language: str | None = None

    model_config = ConfigDict(extra="allow")

    @property
    def ctx(self) -> PostalContext:
        return {"country": get_country_code(self.country), "language": self.language}


class LatLonRow(BaseModel):
    lat: float
    lon: float

    model_config = ConfigDict(extra="allow")


PostalRows: TypeAlias = Generator[PostalRow, None, None]
LatLonRows: TypeAlias = Generator[LatLonRow, None, None]
GeocodingResults: TypeAlias = (
    Generator[GeocodingResult, None, None] | Iterator[GeocodingResult]
)


class Writer(_Writer):
    def __init__(self, uri: Uri, output_format: Formats = Formats.ftm) -> None:
        super().__init__(uri)
        self.output_format = output_format
        self.fieldnames = []
        self.handler = None
        self.writer = None

    def write(self, data: Any) -> None:
        if self.output_format == Formats.csv and not self.fieldnames:
            self.fieldnames = data.keys()
            if self.can_write_parallel:
                self.handler = SmartHandler(self.uri, mode="a")
                self.writer = csv.DictWriter(self.handler.open(), self.fieldnames)
                self.writer.writeheader()

        super().write(data)

    def _write_flush(self) -> None:
        if self.output_format == Formats.csv:
            with smart_open(ensure_uri(self.uri), mode="w") as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writeheader()
                writer.writerows(self.buffer)
        else:
            super()._write_flush()

    def _write_parallel(self, data: Any) -> None:
        if self.output_format == Formats.csv:
            if self.writer is not None:
                self.writer.writerow(data)
        else:
            super()._write_parallel(data)

    def flush(self) -> None:
        if self.handler is not None:
            self.handler.close()
        super().flush()


def read_postal_csv(input_uri: Uri) -> PostalRows:
    with smart_open(input_uri, mode="r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield PostalRow(**row)


def read_latlon_csv(input_uri: Uri) -> LatLonRows:
    with smart_open(input_uri, mode="r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield LatLonRow(**row)


def write_geocode_results(output_uri: Uri, results: GeocodingResults) -> None:
    with smart_open(output_uri, "w") as f:
        writer = csv.DictWriter(f, fieldnames=GeocodingResult.model_fields)
        writer.writeheader()
        writer.writerows(r.model_dump(mode="json") for r in results)


def read_geocode_results_csv(input_uri: Uri) -> GeocodingResults:
    with smart_open(input_uri, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield GeocodingResult(**row)
