from functools import cache, lru_cache
from typing import Generator

import dataset
from dataset.database import Database
from dataset.table import Table
from followthemoney.util import make_entity_id
from normality import normalize

from .logging import get_logger
from .model import AddressInput, GeocodingResult, PostalContext, get_address_id
from .settings import CACHE_TABLE, DATABASE_URI

log = get_logger(__name__)


@lru_cache(1_000_000)
def get_cache_key(value: str, **ctx: PostalContext) -> str:
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

    def put(self, row: GeocodingResult):
        row.cache_key = get_cache_key(row.original_line, country=row.country)
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

    def put(self, row: GeocodingResult):
        bulk = self.bulk()
        bulk.put(row)
        bulk.flush()

    def bulk(self) -> BulkWrite:
        return BulkWrite()

    def get(self, data: AddressInput, **ctx) -> GeocodingResult | None:
        table = self.get_table()
        if isinstance(data, str):
            for res in table.find(cache_key=get_cache_key(data, **ctx)):
                return GeocodingResult(**res)
        address_id = get_address_id(data, **ctx)
        for res in table.find(address_id=address_id):
            return GeocodingResult(**res)
        for res in table.find(canonical_id=address_id):
            return GeocodingResult(**res)

    def iterate(self) -> Generator[GeocodingResult, None, None]:
        with get_connection() as tx:
            for row in tx[CACHE_TABLE]:
                yield GeocodingResult(**row)


cache = Cache()
cache.ensure_index()
