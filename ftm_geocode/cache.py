"""
Cache module for geocoding results.

Uses anystore for flexible backend storage (filesystem, Redis, S3, etc.).
"""

from functools import cache

from anystore.logging import get_logger
from anystore.store import BaseStore

from ftm_geocode.parsing import normalize_for_cache
from ftm_geocode.settings import Settings

log = get_logger(__name__)
settings = Settings()


def make_cache_key(value: str, use_cache: bool = True, **kwargs) -> str | None:
    """
    Generate a cache key for an address string.

    Args:
        value: Address string
        use_cache: If False, returns None (no caching)
        **kwargs: Additional context (country, etc.)

    Returns:
        Cache key string or None
    """
    if not use_cache:
        return None
    return normalize_for_cache(value, country=kwargs.get("country"))


@cache
def get_cache() -> BaseStore:
    """
    Get the configured cache store.

    Returns a singleton instance of the cache store.
    """
    from ftm_geocode.model import GeocodingResult

    store = settings.store.to_store()
    store.key_prefix = store.key_prefix or "ftm-geocode"
    store.model = GeocodingResult
    store.store_none_values = False
    return store
