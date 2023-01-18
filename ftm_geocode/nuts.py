"""
apply nuts codes to geocoded address

https://ec.europa.eu/eurostat/web/gisco/geodata/reference-data/administrative-units-statistical-units/nuts
"""

from functools import cache, lru_cache

import geopandas as gpd
from followthemoney.proxy import E
from pydantic import BaseModel
from shapely.geometry import Point

from .logging import get_logger
from .settings import NUTS_DATA

log = get_logger(__name__)


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


@lru_cache
def get_nuts_codes(lon: float, lat: float) -> Nuts | None:
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
