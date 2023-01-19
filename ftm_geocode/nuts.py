"""
apply nuts codes to geocoded address

https://ec.europa.eu/eurostat/web/gisco/geodata/reference-data/administrative-units-statistical-units/nuts
https://en.wikipedia.org/wiki/Nomenclature_of_Territorial_Units_for_Statistics
"""

from functools import cache, lru_cache
from typing import Any, TypeVar

import geopandas as gpd
from followthemoney.proxy import E
from pydantic import BaseModel
from shapely.geometry import Point

from .logging import get_logger
from .settings import NUTS_DATA
from .util import get_country_name

log = get_logger(__name__)


N = TypeVar("N", bound="Nuts")
N3 = TypeVar("N3", bound="Nuts3")


class Nuts(BaseModel):
    level: int
    code: str
    name: str
    country: str
    country_name: str
    path: str

    @classmethod
    def from_code(cls, code: str) -> N:
        country = code[:2]
        return cls(
            level=len(code) - 2,
            code=code,
            name=get_nuts_name(code),
            country=country,
            country_name=get_country_name(country),
            path=get_nuts_path(code),
        )


class Nuts3(BaseModel):
    nuts1: str
    nuts1_id: str
    nuts2: str
    nuts2_id: str
    nuts3: str
    nuts3_id: str
    country: str
    country_name: str
    path: str

    @classmethod
    def from_code(cls, code: str) -> N3:
        nuts = split_nuts3(code)
        c, n1, n2, n3 = nuts
        return cls(
            nuts1=get_nuts_name(n1),
            nuts1_id=n1,
            nuts2=get_nuts_name(n2),
            nuts2_id=n2,
            nuts3=get_nuts_name(n3),
            nuts3_id=n3,
            country=c,
            country_name=get_country_name(c),
            path="/".join(nuts),
        )


def split_nuts3(code: str) -> tuple[str, str, str, str]:
    # country, nuts1, nuts2, nuts3
    return code[:2], code[:3], code[:4], code[:5]


@cache
def get_nuts_data():
    log.info("Loading nuts shapefile", fp=NUTS_DATA)
    df = gpd.read_file(NUTS_DATA)
    df = df[["LEVL_CODE", "NUTS_ID", "NUTS_NAME", "geometry"]]
    return df


@cache
def get_nuts_names():
    df = get_nuts_data()
    df = df[["NUTS_ID", "NUTS_NAME"]].drop_duplicates().set_index("NUTS_ID")
    return df["NUTS_NAME"].T.to_dict()


def get_nuts_name(code: str) -> str:
    names = get_nuts_names()
    return names[code]


def get_nuts_path(code: str) -> str:
    return "/".join([code[: i + 2] for i in range(len(code) - 1)])


@lru_cache(1_000_000)
def _get_nuts(lon: float, lat: float) -> N3 | None:
    df = get_nuts_data()
    df = df[df["LEVL_CODE"] == 3]
    point = Point(lon, lat)
    res = df[df.contains(point)].drop_duplicates(subset=("NUTS_ID",))
    if res.empty:
        return
    if len(res) > 1:
        log.error("Invalid nuts lookup result, got %d values instead of 1" % len(res))
        return
    for _, row in res.iterrows():
        return Nuts3.from_code(row["NUTS_ID"])


def get_nuts(lon: Any | None = None, lat: Any | None = None) -> Nuts | None:
    try:
        lon, lat = round(float(lon), 6), round(float(lat), 6)
        return _get_nuts(lon, lat)
    except ValueError:
        log.error("Invalid coordinates: (%s, %s)" % (lon, lat))


def get_proxy_nuts(proxy: E) -> N3 | None:
    if not proxy.schema.is_a("Address"):
        return
    try:
        lon, lat = float(proxy.first("longitude")), float(proxy.first("latitude"))
        lon, lat = round(lon, 6), round(lat, 6)  # EU shapefile precision
        return get_nuts(lon, lat)
    except ValueError:
        log.error("Invalid coords", proxy=proxy.to_dict())
        return
