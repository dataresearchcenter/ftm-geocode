"""
Utility functions.
"""

from typing import Any, Iterable
from unicodedata import normalize as _unormalize

from banal import ensure_list
from ftmq.util import get_country_code, get_country_name  # noqa: F401
from normality import normalize as _normalize
from normality import squash_spaces


def get_first(value: str | Iterable[Any] | None, default: Any | None = None) -> Any:
    """Get first value from a list or return default."""
    for v in ensure_list(value):
        return v
    return default


def normalize(value: str) -> str:
    """Normalize a string for geocoding queries."""
    return _unormalize("NFC", squash_spaces(value))


def normalize_google(value: str) -> str:
    """
    Normalize for Google geocoder.

    Google errors on non-UTF-8 strings.
    """
    return ", ".join(_normalize(v, lowercase=False) for v in value.split(","))
