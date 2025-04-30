from typing import Generator, Iterator, Literal, TypeAlias

from ftmq.util import get_country_code
from pydantic import BaseModel, ConfigDict

from ftm_geocode.logging import get_logger
from ftm_geocode.model import GeocodingResult, PostalContext

log = get_logger(__name__)


FORMAT_FTM = "ftm"
Formats: TypeAlias = Literal["csv", "json", "ftm"]


class PostalRow(BaseModel):
    original_line: str
    formatted_line: str | None = None
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
