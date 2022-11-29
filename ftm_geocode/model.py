from collections import defaultdict
from datetime import datetime
from typing import Any, TypedDict

import lazy_import
from banal import clean_dict
from followthemoney import model
from followthemoney.proxy import E, EntityProxy
from followthemoney.util import make_entity_id
from normality import collapse_spaces, normalize
from pydantic import BaseModel, create_model
from zavod.parse.addresses import format_line

from .util import clean_country_codes, clean_country_names, get_country_code, get_first


class GeocodingResult(BaseModel):
    cache_key: str | None = None
    address_id: str
    canonical_id: str
    original_line: str
    result_line: str
    country: str
    lat: float
    lon: float
    geocoder: str
    geocoder_place_id: str | None = None
    geocoder_raw: str | None = None
    ts: datetime


# https://github.com/openvenues/libpostal#parser-labels
# postal -> ftm
# FIXME extend ftm schema to align with postal output?
MAPPING = (
    # venue name e.g. "Brooklyn Academy of Music", and building names e.g. "Empire State Building"
    ("house", "remarks"),
    # for category queries like "restaurants", etc.
    ("category", "keywords"),
    # phrases like "in", "near", etc. used after a category phrase to help with parsing queries like "restaurants in Brooklyn"
    ("near", "remarks"),
    # usually refers to the external (street-facing) building number. In some countries this may be a compount, hyphenated number which also includes an apartment number, or a block number (a la Japan), but libpostal will just call it the house_number for simplicity.
    ("house_number", "remarks"),
    # street name(s)
    ("road", "street"),
    # an apartment, unit, office, lot, or other secondary unit designator
    ("unit", "remarks"),
    # expressions indicating a floor number e.g. "3rd Floor", "Ground Floor", etc.
    ("level", "remarks"),
    # numbered/lettered staircase
    ("staircase", "remarks"),
    # numbered/lettered entrance
    ("entrance", "remarks"),
    # post office box: typically found in non-physical (mail-only) addresses
    ("po_box", "postOfficeBox"),
    # postal codes used for mail sorting
    ("postcode", "postalCode"),
    # usually an unofficial neighborhood name like "Harlem", "South Bronx", or "Crown Heights"
    ("suburb", "remarks"),
    # these are usually boroughs or districts within a city that serve some official purpose e.g. "Brooklyn" or "Hackney" or "Bratislava IV"
    ("city_district", "remarks"),
    # any human settlement including cities, towns, villages, hamlets, localities, etc.
    ("city", "city"),
    # named islands e.g. "Maui"
    ("island", "region"),
    # usually a second-level administrative division or county.
    ("state_district", "region"),
    # a first-level administrative division. Scotland, Northern Ireland, Wales, and England in the UK are mapped to "state" as well (convention used in OSM, GeoPlanet, etc.)
    ("state", "state"),
    # informal subdivision of a country without any political status
    ("country_region", "region"),
    # sovereign nations and their dependent territories, anything with an ISO-3166 code.
    ("country", "country"),
    # currently only used for appending “West Indies” after the country name, a pattern frequently used in the English-speaking Caribbean e.g. “Jamaica, West Indies”
    ("world_region", "region"),
)

Values = list[str] | None


class PostalContext(TypedDict):
    language: str | None = ""
    country: str | None = ""


class AddressBase(BaseModel):
    def get_country(self) -> str:
        return ";".join(self.country or [])

    def get_first(self, attr, default: Any | None = None) -> str | None:
        return get_first(getattr(self, attr, None), default)

    def get_id(self) -> str:  # serves as cache key
        if hasattr(self, "_id"):
            return self._id
        ident = make_entity_id(normalize(self.get_formatted_line()))
        country = self.get_first("country")
        if country:
            ident = f"{country.lower()}-{ident}"
        return f"addr-{ident}"

    def to_dict(self) -> dict[str, list[str]]:
        return clean_dict(dict(self))


class PostalAddressBase(AddressBase):
    country_code: Values = None

    def __init__(self, **data):
        data["country"] = clean_country_names(data.get("country"))
        data["country_code"] = clean_country_codes(data.get("country"))
        super().__init__(**data)

    def get_formatted_line(self) -> str:
        return format_line(
            summary=collapse_spaces(
                " ".join(
                    (
                        self.get_first("house", ""),
                        self.get_first("house_number", ""),
                        self.get_first("near", ""),
                    )
                )
            )
            or None,  # noqa
            po_box=self.get_first("po_box"),
            street=self.get_first("street"),
            postal_code=self.get_first("postcode"),
            city=self.get_first("city"),
            state=self.get_first("state"),
            country_code=self.get_first("country_code"),
        )

    @classmethod
    def from_postal_result(
        cls, input_data: list[tuple[str, str]], **ctx: PostalContext
    ) -> "PostalAddress":
        data = defaultdict(set)
        for value, key in input_data:
            data[key].add(value)
        if "country" in ctx:
            data["country"].add(ctx["country"])
        return cls(**data)

    @classmethod
    def from_string(cls, value: str, **ctx: PostalContext) -> "PostalAddress":
        parse_address = lazy_import.lazy_callable("postal.parser.parse_address")
        # postal screams if language or country is None
        ctx = {k: ctx.get(k, "") for k in ("language", "country")}
        result = parse_address(value, **ctx)
        return cls.from_postal_result(result, **ctx)


PostalAddress: PostalAddressBase = create_model(
    "PostalAddress",
    **{m[0]: (Values, None) for m in MAPPING},
    __base__=PostalAddressBase,
)

FtmAddressBase: AddressBase = create_model(
    "FtmAddress",
    **{p: (Values, None) for p in model.get("Address").properties},
    __base__=AddressBase,
)


class Address(FtmAddressBase):
    def to_proxy(self) -> E:
        return model.get_proxy(
            {
                "id": self.get_id(),
                "schema": "Address",
                "properties": clean_dict(self.dict()),
            }
        )

    def get_formatted_line(self) -> str:
        return format_line(
            summary=collapse_spaces(
                " ".join((self.get_first("summary", ""), " ".join(self.remarks or [])))
            ),
            po_box=self.get_first("postOfficeBox"),
            street=self.get_first("street"),
            postal_code=self.get_first("postalCode"),
            city=self.get_first("city"),
            state=self.get_first("state"),
            country_code=get_country_code(self.get_first("country")),
        )

    @classmethod
    def from_postal(cls, input_data: PostalAddress, **ctx: PostalContext) -> "Address":
        mapping = dict(MAPPING)
        data = defaultdict(set)
        data["country"].add(ctx.get("country"))
        for key, values in input_data:
            if key == "country_code":
                key = "country"
            if values is not None:
                data[mapping[key]].update(values)
        data["country"] = clean_country_codes(data["country"])
        return cls(**data)

    @classmethod
    def from_string(cls, value: str, **ctx: PostalContext) -> "Address":
        return cls.from_postal(PostalAddress.from_string(value, **ctx))

    @classmethod
    def from_result(cls, result: GeocodingResult) -> "Address":
        ctx = {"country": result.country}
        address = cls.from_postal(PostalAddress.from_string(result.result_line, **ctx))
        address.full = [result.result_line]
        address.latitude = [str(result.lat)]
        address.longitude = [str(result.lon)]
        return address

    @classmethod
    def from_proxy(cls, proxy: E) -> "Address":
        data = proxy.to_dict()
        address = cls(**data["properties"])
        address._id = proxy.id
        return address


AddressInput = str | Address | PostalAddress | E | GeocodingResult


def get_address(data: AddressInput, **ctx: PostalContext) -> Address:
    if isinstance(data, str):
        return Address.from_string(data, **ctx)
    if isinstance(data, PostalAddress):
        return Address.from_postal(data, **ctx)
    if isinstance(data, EntityProxy):
        return Address.from_proxy(data)
    if isinstance(data, GeocodingResult):
        return Address.from_result(data)
    return data


def get_formatted_line(data: AddressInput, **ctx: PostalContext) -> str:
    address = get_address(data, **ctx)
    return address.get_formatted_line()


def get_address_id(data: AddressInput, **ctx: PostalContext) -> str:
    address = get_address(data, **ctx)
    return address.get_id()
