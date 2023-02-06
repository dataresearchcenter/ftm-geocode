from functools import cache, lru_cache
from typing import Generator

import dataset
from dataset.database import Database
from dataset.table import Table
from followthemoney.util import make_entity_id
from normality import normalize

from .logging import get_logger
from .model import GeocodingResult, PostalContext, get_address_id
from .settings import CACHE_TABLE, DATABASE_URI
from .util import normalize as unormalize

log = get_logger(__name__)


@lru_cache(1_000_000)
def get_cache_key(value: str, **ctx: PostalContext) -> str:
    value = unormalize(value)  # FIXME erf
    country = ctx.get("country")
    ident = make_entity_id(normalize(value))
    if country is not None:
        return f"{country.lower()}-{ident}"
    return ident


@cache
def get_connection() -> Database:
    return dataset.connect(DATABASE_URI)


class BulkWrite:
    def __init__(self, limit: int | None = 10_000):
        self.limit = limit
        self.rows: list[GeocodingResult] = []
        self.i = 0

    def put(self, row: GeocodingResult, cache_key: str | None = None):
        if cache_key is None:
            row.cache_key = get_cache_key(row.original_line, country=row.country)
        else:
            row.cache_key = cache_key
        self.rows.append(dict(row))
        self.i += 1
        if self.i % self.limit == 0:
            self.flush()

    def flush(self):
        with get_connection() as tx:
            tx[CACHE_TABLE].insert_many(self.rows)
            self.rows = []
            log.info(f"Cache: insert {self.i} results.")


class Cache:
    indexes = (
        ("ix", "cache_key"),
        ("aix", "address_id"),
        ("cix", "canonical_id"),
    )

    def __str__(self) -> str:
        return f"<GeoCache `{DATABASE_URI}`>"

    def ensure_index(self):
        with get_connection() as tx:
            has_data = tx[CACHE_TABLE].find_one()
            if has_data is not None:
                log.info("Ensuring indexes...")
                for name, field in self.indexes:
                    tx.query(
                        f"CREATE INDEX IF NOT EXISTS {name} ON {CACHE_TABLE}({field})"
                    )
                log.info("...done")

    def get_table(self) -> Table:
        db = get_connection()
        return db[CACHE_TABLE]

    def put(self, row: GeocodingResult, cache_key: str | None = None):
        bulk = self.bulk()
        bulk.put(row, cache_key)
        bulk.flush()

    def bulk(self) -> BulkWrite:
        return BulkWrite()

    def get(self, address_line: str, **ctx: PostalContext) -> GeocodingResult | None:
        return _lru_from_cache(address_line, **ctx)

    def iterate(self) -> Generator[GeocodingResult, None, None]:
        with get_connection() as tx:
            for row in tx[CACHE_TABLE]:
                yield GeocodingResult(**row)


@cache
def get_cache():
    c = Cache()
    c.ensure_index()
    return c


@lru_cache(10_000)
def _lru_from_cache(address_line: str, **ctx: PostalContext) -> GeocodingResult | None:
    info = _lru_from_cache.cache_info()
    if int(info.hits / 1000) % 100 == 0:
        log.info(
            f"Cache hits: {info.hits}, misses: {info.misses}, currsize: {info.currsize}"
        )
    c = get_cache()
    cache_key = get_cache_key(address_line, **ctx)
    table = c.get_table()
    for res in table.find(cache_key=cache_key, order_by="-ts"):
        return GeocodingResult(**res)
    address_id = get_address_id(address_line, **ctx)
    for res in table.find(address_id=address_id, order_by="-ts"):
        res = GeocodingResult(**res)
        c.put(res, cache_key)
        return res
    for res in table.find(canonical_id=address_id, order_by="-ts"):
        res = GeocodingResult(**res)
        c.put(res, cache_key)
        return res
