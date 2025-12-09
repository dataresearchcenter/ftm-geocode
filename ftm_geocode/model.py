from collections import defaultdict
from datetime import datetime
from typing import Any, Self, TypeAlias, TypedDict

import lazy_import
import orjson
from anystore.types import SDict
from anystore.util import clean_dict
from banal import is_mapping
from followthemoney import EntityProxy, ValueEntity
from followthemoney.util import join_text
from ftmq.util import clean_string, make_entity
from normality import squash_spaces
from pydantic import BaseModel, field_validator, model_validator
from rigour.addresses import clean_address, format_address_line

from ftm_geocode.cache import make_cache_key
from ftm_geocode.nuts import get_nuts
from ftm_geocode.settings import GEOCODERS, Settings
from ftm_geocode.util import (
    clean_country_codes,
    clean_country_names,
    get_country_code,
    get_first,
    make_address_id,
)

settings = Settings()
USE_LIBPOSTAL = settings.libpostal

Values: TypeAlias = list[str] | None


class PostalContext(TypedDict):
    language: str | None
    country: str | None


class GeocodingResult(BaseModel):
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
    def nuts(self) -> tuple[str, str, str] | None:
        if self.nuts1_id:
            return (self.nuts1_id, self.nuts2_id, self.nuts3_id)

    def apply_nuts(self) -> None:
        if not self.nuts1_id or not self.nuts2_id or not self.nuts3_id:
            nuts = get_nuts(self.lon, self.lat)
            if nuts is not None:
                self.nuts1_id = nuts.nuts1_id
                self.nuts2_id = nuts.nuts2_id
                self.nuts3_id = nuts.nuts3_id

    def to_proxy(self) -> ValueEntity:
        address = Address.from_result(self)
        proxy = address.to_proxy()
        proxy.add("region", self.nuts)
        return proxy

    @model_validator(mode="before")
    @classmethod
    def make_cache_key(cls, data: SDict) -> SDict:
        data["cache_key"] = make_cache_key(
            data["original_line"], country=data.get("country")
        )
        return data

    @field_validator("geocoder_place_id", mode="before")
    @classmethod
    def to_str(cls, value) -> str | None:
        return clean_string(value)

    @field_validator("geocoder_raw", mode="before")
    @classmethod
    def to_dict(cls, value: Any) -> dict[str, Any]:
        if is_mapping(value):
            return value
        if isinstance(value, (str, bytes)):
            return orjson.loads(value)
        return {}


# libpostal parser labels -> FTM Address properties
# https://github.com/openvenues/libpostal#parser-labels
POSTAL_TO_FTM = {
    "full": "full",
    "house": "remarks",  # venue/building names
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
    "country": "country",
    "country_code": "country",
    "world_region": "region",
}

POSTAL_KEYS = list(POSTAL_TO_FTM.keys())


class PostalAddress(BaseModel):
    """Intermediate representation of a parsed address from libpostal."""

    # libpostal fields
    full: Values = None
    house: Values = None
    category: Values = None
    near: Values = None
    house_number: Values = None
    road: Values = None
    unit: Values = None
    level: Values = None
    staircase: Values = None
    entrance: Values = None
    po_box: Values = None
    postcode: Values = None
    suburb: Values = None
    city_district: Values = None
    city: Values = None
    island: Values = None
    state_district: Values = None
    state: Values = None
    country_region: Values = None
    country: Values = None
    country_code: Values = None
    world_region: Values = None

    def __init__(self, **data):
        data["country"] = clean_country_names(data.get("country"))
        data["country_code"] = clean_country_codes(data.get("country"))
        super().__init__(**data)

    def get_first(self, attr: str, default: Any | None = None) -> str | None:
        return get_first(getattr(self, attr, None), default)

    def get_formatted_line(self) -> str:
        country = self.get_first("country")
        data = {
            "attention": self.get_first("near"),
            "house": join_text(self.get_first("house"), self.get_first("po_box")),
            "house_number": self.get_first("house_number"),
            "road": self.get_first("street") or self.get_first("road"),
            "postcode": self.get_first("postcode"),
            "city": self.get_first("city"),
            "state": self.get_first("state"),
            "country": country,
        }
        return format_address_line(data, country=country)

    def to_dict(self) -> dict[str, str | None]:
        """Return single-valued dict (first value of each field)."""
        return clean_dict({k: get_first(v) for k, v in self.model_dump().items()})

    @classmethod
    def from_postal_result(
        cls, input_data: list[tuple[str, str]], **ctx: PostalContext
    ) -> Self:
        data = defaultdict(set)
        for value, key in input_data:
            data[key].add(value.title())
        if "country" in ctx:
            data["country"].add(ctx["country"])
        return cls(**data)

    @classmethod
    def from_string(cls, value: str, **ctx: PostalContext) -> Self:
        value = clean_address(value)
        if USE_LIBPOSTAL:
            parse_address = lazy_import.lazy_callable("postal.parser.parse_address")
            # postal requires non-None values
            postal_ctx = {k: ctx.get(k, "") or "" for k in ("language", "country")}
            result = parse_address(value, **postal_ctx)
            if "full" not in dict(result):
                result.append((value, "full"))
        else:
            result = [(value, "full")]
        return cls.from_postal_result(result, **ctx)


class Address(BaseModel):
    """FTM Address entity representation."""

    # Core address fields
    full: Values = None
    remarks: Values = None
    postOfficeBox: Values = None
    street: Values = None
    street2: Values = None
    city: Values = None
    postalCode: Values = None
    region: Values = None
    state: Values = None
    latitude: Values = None
    longitude: Values = None
    country: Values = None
    osmId: Values = None
    googlePlaceId: Values = None

    # Private fields
    _id: str | None = None
    _postal: PostalAddress | None = None

    def get_first(self, attr: str, default: Any | None = None) -> str | None:
        return get_first(getattr(self, attr, None), default)

    def get_country(self) -> str:
        return ";".join(self.country or [])

    def get_id(self) -> str:
        if self._id:
            return self._id
        osm_id = self.get_first("osmId")
        google_id = self.get_first("googlePlaceId")
        if osm_id:
            return f"addr-osm-{osm_id}"
        if google_id:
            return f"addr-google-{google_id}"
        return make_address_id(self.get_formatted_line(), self.get_first("country"))

    def get_formatted_line(self) -> str:
        country = get_country_code(self.get_first("country"))
        data = {
            "attention": squash_spaces(
                " ".join((self.get_first("summary", ""), " ".join(self.remarks or [])))
            ),
            "house": self.get_first("postOfficeBox"),
            "road": (
                self.get_first("road")
                or self.get_first("street")
                or self.get_first("full")
            ),
            "postcode": self.get_first("postalCode"),
            "city": self.get_first("city"),
            "state": self.get_first("state"),
        }
        return format_address_line(data, country=country)

    def to_dict(self) -> dict[str, list[str]]:
        data = clean_dict(self.model_dump())
        data["full"] = [self.get_formatted_line()]
        return data

    def to_proxy(self) -> ValueEntity:
        proxy = make_entity(
            {
                "id": self.get_id(),
                "schema": "Address",
                "properties": clean_dict(self.model_dump()),
            },
        )
        proxy.set("full", self.get_formatted_line())
        return proxy

    @classmethod
    def from_postal(cls, postal: PostalAddress, **ctx: PostalContext) -> Self:
        """Convert PostalAddress to FTM Address using field mapping."""
        data: dict[str, set] = defaultdict(set)
        data["country"].add(ctx.get("country"))

        for postal_key, ftm_key in POSTAL_TO_FTM.items():
            if postal_key == "country_code":
                ftm_key = "country"
            values = getattr(postal, postal_key, None)
            if values is not None:
                data[ftm_key].update(values)

        data["country"] = clean_country_codes(data["country"])
        instance = cls(**data)
        instance._postal = postal
        return instance

    @classmethod
    def from_string(cls, value: str, **ctx: PostalContext) -> Self:
        value = clean_address(value)
        postal = PostalAddress.from_string(value, **ctx)
        return cls.from_postal(postal, **ctx)

    @classmethod
    def from_result(cls, result: GeocodingResult) -> Self:
        ctx: PostalContext = {"country": result.country, "language": None}
        address = cls.from_string(result.result_line, **ctx)
        address.full = [result.result_line]
        address.longitude = [str(result.lon)]
        address.latitude = [str(result.lat)]
        if result.geocoder == GEOCODERS.nominatim.name:
            address.osmId = [result.geocoder_place_id]
        if result.geocoder == GEOCODERS.google.name:
            address.googlePlaceId = [result.geocoder_place_id]
        return address

    @classmethod
    def from_proxy(cls, proxy: EntityProxy) -> Self:
        data = proxy.to_dict()
        address = cls(**data["properties"])
        address._id = proxy.id
        return address


AddressInput: TypeAlias = str | Address | PostalAddress | EntityProxy | GeocodingResult


def get_address(
    data: AddressInput, address_id: str | None = None, **ctx: PostalContext
) -> Address:
    if isinstance(data, str):
        addr = Address.from_string(data, **ctx)
    elif isinstance(data, PostalAddress):
        addr = Address.from_postal(data, **ctx)
    elif isinstance(data, EntityProxy):
        addr = Address.from_proxy(data)
    elif isinstance(data, GeocodingResult):
        addr = Address.from_result(data)
    else:
        raise ValueError(f"Invalid input format: {data}")
    if address_id is not None:
        addr._id = address_id
    return addr


def get_components(data: AddressInput, **ctx: PostalContext) -> dict[str, str | None]:
    if isinstance(data, PostalAddress):
        return data.to_dict()
    if isinstance(data, Address):
        if data._postal is not None:
            return data._postal.to_dict()
        # No postal data, parse from full address
        full = data.get_first("full") or data.get_formatted_line()
        return PostalAddress.from_string(full, **ctx).to_dict()

    if isinstance(data, str):
        postal = PostalAddress.from_string(data, **ctx)
    elif isinstance(data, EntityProxy):
        postal = PostalAddress.from_string(data.caption, **ctx)
    elif isinstance(data, GeocodingResult):
        postal = PostalAddress.from_string(data.result_line, **ctx)
    else:
        raise NotImplementedError(data)

    return postal.to_dict()


def get_formatted_line(data: AddressInput, **ctx: PostalContext) -> str:
    address = get_address(data, **ctx)
    return address.get_formatted_line()


def get_canonical_id(geocoder: GEOCODERS, place_id: str) -> str:
    if geocoder == GEOCODERS.nominatim:
        return f"addr-osm-{place_id}"
    return f"addr-{geocoder.value}-{place_id}"


def get_coords(data: AddressInput, **ctx: PostalContext) -> tuple[float, float] | None:
    address = get_address(data, **ctx)
    try:
        return float(get_first(address.longitude)), float(get_first(address.latitude))
    except (ValueError, TypeError):
        return None
