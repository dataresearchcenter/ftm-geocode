from typing import Any, Generator, Iterable
from unicodedata import normalize as _unormalize

from addressformatting import AddressFormatter
from banal import ensure_list
from followthemoney.types import registry
from ftmq.util import get_country_code, get_country_name
from nomenklatura.entity import CE
from normality import collapse_spaces
from normality import normalize as _normalize

formatter = AddressFormatter()


def format_line(data: dict[str, str | None], country: str) -> str:
    return formatter.one_line(data, country)


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


def get_proxy_addresses(proxy: CE) -> Generator[str, None, None]:
    if proxy.schema.is_a("Address"):
        yield proxy.caption
    else:
        for value in proxy.get_type_values(registry.address):
            yield value


def apply_address(proxy: CE, address: CE, rewrite_id: bool | None = True) -> CE:
    if proxy.schema.is_a("Address"):
        if rewrite_id:
            proxy.id = address.id
        else:
            address.id = proxy.id
        return proxy.merge(address)
    proxy.add("addressEntity", address.id)  # FIXME delete old reference?
    proxy.add("address", address.caption)
    proxy.add("country", address.get("country"))
    return proxy
