from functools import cache

from anystore.store import BaseStore, get_store
from followthemoney.util import make_entity_id
from ftmq.util import clean_string, get_country_code
from normality import normalize

from ftm_geocode.logging import get_logger
from ftm_geocode.settings import Settings
from ftm_geocode.util import normalize as unormalize

log = get_logger(__name__)
settings = Settings()


def make_cache_key(value, **kwargs) -> str | None:
    if kwargs.get("use_cache") is False:
        return
    value = clean_string(value)
    if not value:
        return
    key = normalize(unormalize(value))  # FIXME erf
    key = make_entity_id(key)
    country = get_country_code(kwargs.get("country"))
    if country:
        key = f"{country}-{key}"
    return f"{settings.cache_prefix}/{key}"


@cache
def get_cache() -> BaseStore:
    from ftm_geocode.model import GeocodingResult

    kwargs = settings.cache.model_dump()
    kwargs["model"] = GeocodingResult
    kwargs["store_none_values"] = False
    return get_store(**kwargs)
