"""
Data models for geocoding results.

This module contains pure data classes without business logic.
"""

from datetime import datetime
from typing import Any

import orjson
from anystore.types import SDict
from banal import is_mapping
from ftmq.util import clean_string
from pydantic import BaseModel, field_validator, model_validator

from ftm_geocode.nuts import get_nuts
from ftm_geocode.parsing import normalize_for_cache


class GeocodingResult(BaseModel):
    """Result from a geocoding operation."""

    cache_key: str
    address_id: str
    original_line: str
    result_line: str
    country: str
    lon: float
    lat: float
    geocoder: str
    geocoder_place_id: str | None = None
    geocoder_raw: dict[str, Any] | None = None
    nuts1_id: str | None = None
    nuts2_id: str | None = None
    nuts3_id: str | None = None
    ts: datetime | None = None

    @property
    def nuts(self) -> tuple[str, str | None, str | None] | None:
        """Get NUTS region tuple if available."""
        if self.nuts1_id:
            return (self.nuts1_id, self.nuts2_id, self.nuts3_id)
        return None

    def apply_nuts(self) -> None:
        """Apply NUTS codes based on coordinates."""
        if not self.nuts1_id or not self.nuts2_id or not self.nuts3_id:
            nuts = get_nuts(self.lon, self.lat)
            if nuts is not None:
                self.nuts1_id = nuts.nuts1_id
                self.nuts2_id = nuts.nuts2_id
                self.nuts3_id = nuts.nuts3_id

    @model_validator(mode="before")
    @classmethod
    def _make_cache_key(cls, data: SDict) -> SDict:
        """Generate cache key from original line and country."""
        if "cache_key" not in data or data["cache_key"] is None:
            data["cache_key"] = normalize_for_cache(
                data["original_line"], country=data.get("country")
            )
        return data

    @field_validator("geocoder_place_id", mode="before")
    @classmethod
    def _clean_place_id(cls, value) -> str | None:
        return clean_string(value)

    @field_validator("geocoder_raw", mode="before")
    @classmethod
    def _parse_raw(cls, value: Any) -> dict[str, Any]:
        if is_mapping(value):
            return dict(value)
        if isinstance(value, (str, bytes)):
            return orjson.loads(value)
        return {}
