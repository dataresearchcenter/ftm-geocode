from functools import cache
from typing import Generator

import dataset
from dataset.database import Database
from dataset.table import Table
from ftmstore.settings import DATABASE_URI
from normality import normalize as nnormalize

from .logging import get_logger
from .model import AddressInput, GeocodingResult, get_address
from .settings import CACHE_TABLE
from .util import normalize, normalize_google

log = get_logger(__name__)


@cache
def get_connection() -> Database:
    return dataset.connect(DATABASE_URI)


def get_lookup_lines(value: str) -> Generator[str, None, None]:
    # erf
    yield value
    yield value.strip()
    yield normalize(value)
    yield nnormalize(value, lowercase=False)
    yield nnormalize(value)
    yield normalize_google(value)
    yield normalize_google(value).replace(",", "")


class BulkWrite:
    limit = 10_000
    rows: list[GeocodingResult] = []
    i = 0

    def put(self, row: GeocodingResult):
        self.rows.append(dict(row))
        self.i += 1
        if self.i % self.limit == 0:
            self.flush()

    def flush(self):
        with get_connection() as tx:
            tx[CACHE_TABLE].insert_many(self.rows)
            self.rows = []
            log.info(f"Insert: {self.i} results.")


class Cache:
    def __str__(self) -> str:
        return f"<GeoCache `{DATABASE_URI}`>"

    def get_table(self) -> Table:
        db = get_connection()
        return db[CACHE_TABLE]

    def put(self, row: GeocodingResult):
        table = self.get_table()
        table.insert(dict(row))

    def bulk(self) -> BulkWrite:
        return BulkWrite()

    def get(
        self, data: AddressInput, original_line: str | None = None, **ctx
    ) -> GeocodingResult | None:
        address = get_address(data, **ctx)
        table = self.get_table()
        res = table.find_one(address_id=address.get_id())
        if res is None and original_line is not None:
            for line in get_lookup_lines(original_line):
                res = table.find_one(original_line=line)
                if res is not None:
                    break
        if res is not None:
            return GeocodingResult(**res)

    def iterate(self) -> Generator[GeocodingResult, None, None]:
        with get_connection() as tx:
            for row in tx[CACHE_TABLE]:
                yield GeocodingResult(**row)


def get_cache() -> Cache:
    return Cache()


cache = get_cache()
