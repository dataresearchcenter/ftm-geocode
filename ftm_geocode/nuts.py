"""
apply nuts codes to geocoded address

https://ec.europa.eu/eurostat/web/gisco/geodata/reference-data/administrative-units-statistical-units/nuts
"""

from functools import cache, lru_cache
from typing import Any

import geopandas as gpd
import pandas as pd
from followthemoney.proxy import E
from pydantic import BaseModel
from shapely.geometry import Point

from .logging import get_logger
from .settings import NUTS_DATA
from .util import get_country_name

log = get_logger(__name__)


LEVELS = {
    # length of code -> level
    2: 0,
    3: 1,
    4: 2,
    5: 3,
}


class Nuts(BaseModel):
    nuts0: str
    nuts0_id: str
    nuts1: str
    nuts1_id: str
    nuts2: str
    nuts2_id: str
    nuts3: str
    nuts3_id: str
    country: str


@cache
def get_nuts_data():
    log.info("Loading nuts shapefile", fp=NUTS_DATA)
    df = gpd.read_file(NUTS_DATA)
    df = df[["NUTS_ID", "LEVL_CODE", "CNTR_CODE", "NUTS_NAME", "geometry"]]
    return df


@cache
def get_nuts_pivot():
    # FIXME this should be simpler
    df = get_nuts_data()
    df = df[["LEVL_CODE", "NUTS_ID"]].drop_duplicates()

    def _pivot():
        for _, nuts0 in df[df["LEVL_CODE"] == 0].iterrows():
            nuts0 = nuts0["NUTS_ID"]
            for _, nuts1 in df[
                (df["LEVL_CODE"] == 1) & df["NUTS_ID"].str.startswith(nuts0)
            ].iterrows():
                nuts1 = nuts1["NUTS_ID"]
                for _, nuts2 in df[
                    (df["LEVL_CODE"] == 2) & df["NUTS_ID"].str.startswith(nuts1)
                ].iterrows():
                    nuts2 = nuts2["NUTS_ID"]
                    for _, nuts3 in df[
                        (df["LEVL_CODE"] == 3) & df["NUTS_ID"].str.startswith(nuts2)
                    ].iterrows():
                        nuts3 = nuts3["NUTS_ID"]
                        yield nuts0, nuts1, nuts2, nuts3

    df = pd.DataFrame(_pivot(), columns=("nuts0", "nuts1", "nuts2", "nuts3"))
    df["path"] = df.apply(lambda x: "/".join(x), axis=1)
    return df


@cache
def get_nuts_names():
    df = get_nuts_data()
    df = df[["NUTS_ID", "NUTS_NAME"]].set_index("NUTS_ID")
    return df["NUTS_NAME"].T.to_dict()


@lru_cache
def get_nuts_name(code: str) -> str:
    names = get_nuts_names()
    return names[code]


def get_nuts_level(code: str) -> int:
    return LEVELS[len(code)]


def get_nuts_country(code: str) -> str:
    return get_country_name(code[:2])


@lru_cache
def get_nuts_path(code: str) -> str:
    df = get_nuts_pivot()
    path = df[df["path"].str.contains(code)].iloc[0]["path"]
    level = get_nuts_level(code)
    return "/".join(path.split("/")[: level + 1])


@lru_cache(1_000_000)
def _get_nuts_codes(lon: float, lat: float) -> Nuts | None:
    df = get_nuts_data()
    point = Point(lon, lat)
    res = (
        df[df.contains(point)]
        .sort_values("NUTS_ID")
        .drop_duplicates(subset=("NUTS_ID",))
    )
    if res.empty:
        return
    if len(res) != 4:
        log.error("Invalid nuts lookup result, got %d values instead of 4" % len(res))
        return
    countries = res["CNTR_CODE"].unique()
    if len(countries) > 1:
        log.error(
            "Invalid nuts lookup result, git %d countries instead of 1" % len(countries)
        )
    data: Nuts = {"country": countries[0]}
    res = res.set_index("LEVL_CODE")
    for level, row in res.iterrows():
        data[f"nuts{level}"] = row["NUTS_NAME"]
        data[f"nuts{level}_id"] = row["NUTS_ID"]
    return Nuts(**data)


def get_nuts_codes(lon: Any | None = None, lat: Any | None = None) -> Nuts | None:
    try:
        lon, lat = round(float(lon), 6), round(float(lat), 6)
        return _get_nuts_codes(lon, lat)
    except ValueError:
        log.error("Invalid coordinates: (%s, %s)" % (lon, lat))


def get_proxy_nuts(proxy: E) -> Nuts | None:
    if not proxy.schema.is_a("Address"):
        return
    try:
        lon, lat = float(proxy.first("longitude")), float(proxy.first("latitude"))
        lon, lat = round(lon, 6), round(lat, 6)  # EU shapefile precision
        return get_nuts_codes(lon, lat)
    except ValueError:
        log.error("Invalid cords", proxy=proxy.to_dict())
        return
