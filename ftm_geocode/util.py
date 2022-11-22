from functools import lru_cache
from typing import Any, Generator, Iterable
from unicodedata import normalize as _unormalize

import countrynames
import pycountry
from banal import ensure_list
from followthemoney.proxy import EntityProxy
from followthemoney.types import registry
from normality import collapse_spaces
from normality import normalize as _normalize


@lru_cache(1_000_000)
def get_country_code(value: str | None) -> str | None:
    if value is None:
        return
    code = countrynames.to_code(value)
    if code is not None:
        return code
    try:
        results = pycountry.countries.search_fuzzy(value)
        for result in results:
            return result.alpha_2
    except LookupError:
        return


@lru_cache(1_000_000)
def get_country_name(code: str | None) -> str | None:
    if code is None:
        return
    code = get_country_code(code)
    try:
        country = pycountry.countries.get(alpha_2=code)
        return country.name
    except LookupError:
        return


def get_first(value: str | Iterable[Any] | None, default: Any | None = None) -> Any:
    value = ensure_list(value)
    if value:
        return value[0]
    return default


def clean_country_codes(values: Iterable[str] | str | None) -> set[str]:
    codes = set()
    for value in ensure_list(values):
        code = get_country_code(value)
        if code is not None:
            codes.add(code)
    return codes


def clean_country_names(values: Iterable[str] | str | None) -> set[str]:
    names = set()
    for value in ensure_list(values):
        name = get_country_name(value)
        if name is not None:
            names.add(name)
    return names


def normalize(value: str) -> str:
    return _unormalize("NFC", collapse_spaces(value))


def normalize_google(value: str) -> str:
    # Google error: "One of the input parameters contains a non-UTF-8 string"
    return ", ".join(_normalize(v, lowercase=False) for v in value.split(","))


def get_proxy_addresses(proxy: EntityProxy) -> Generator[str, None, None]:
    if proxy.schema.is_a("Address"):
        yield proxy.caption
    else:
        for value in proxy.get_type_values(registry.address):
            yield value


def apply_address(
    proxy: EntityProxy, address: EntityProxy, rewrite_id: bool | None = True
) -> EntityProxy:
    if proxy.schema.is_a("Address"):
        if rewrite_id:
            proxy.id = address.id
        else:
            address.id = proxy.id
        return proxy.merge(address)
    proxy.add("addressEntity", address.id)  # FIXME delete old reference?
    proxy.add("address", address.caption)
    return proxy
