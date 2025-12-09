from functools import cache

from anystore.logging import get_logger
from anystore.store import BaseStore

from ftm_geocode.settings import Settings
from ftm_geocode.util import make_address_id

log = get_logger(__name__)
settings = Settings()


def make_cache_key(value, **kwargs) -> str | None:
    if kwargs.get("use_cache") is False:
        return
    return make_address_id(value, **kwargs)


@cache
def get_cache() -> BaseStore:
    from ftm_geocode.model import GeocodingResult

    store = settings.store.to_store()
    store.key_prefix = store.key_prefix or "ftm-geocode"
    store.model = GeocodingResult
    store.store_none_values = False
    return store
