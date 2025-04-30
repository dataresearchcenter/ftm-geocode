from functools import cache

from anystore.store import BaseStore, get_store

from ftm_geocode.logging import get_logger
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

    kwargs = settings.cache.model_dump()
    kwargs["model"] = GeocodingResult
    kwargs["store_none_values"] = False
    return get_store(**kwargs)
