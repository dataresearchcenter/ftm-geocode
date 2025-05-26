from enum import StrEnum
from typing import Optional

import typer
from anystore.cli import ErrorHandler
from anystore.io import (
    FORMAT_CSV,
    FORMAT_JSON,
    ModelWriter,
    Writer,
    smart_stream_models,
)
from ftmq.io import smart_read_proxies, smart_write_proxies
from rich.console import Console
from typing_extensions import Annotated

from ftm_geocode import __version__, logic
from ftm_geocode.cache import get_cache
from ftm_geocode.geocode import GEOCODERS, geocode_line, geocode_proxy
from ftm_geocode.io import FORMAT_FTM, LatLonRow, PostalRow
from ftm_geocode.logging import configure_logging, get_logger
from ftm_geocode.model import POSTAL_KEYS, GeocodingResult, get_address
from ftm_geocode.nuts import get_nuts, get_proxy_nuts
from ftm_geocode.settings import Settings

settings = Settings()
cli = typer.Typer(no_args_is_help=True)
cli_cache = typer.Typer()
cli.add_typer(cli_cache, name="cache")
console = Console(stderr=True)

log = get_logger(__name__)


class Formats(StrEnum):
    ftm = FORMAT_FTM
    json = FORMAT_JSON
    csv = FORMAT_CSV


class IOFormats(StrEnum):
    json = FORMAT_JSON
    csv = FORMAT_CSV


class Opts:
    IN = typer.Option("-", "-i", help="Input uri (file, http, s3...)")
    OUT = typer.Option("-", "-o", help="Output uri (file, http, s3...)")
    FORMATS = typer.Option(Formats.ftm)
    IOFORMATS = typer.Option(Formats.json)
    GEOCODERS = typer.Option(settings.geocoders, "--geocoders", "-g")
    APPLY_NUTS = typer.Option(False, help="Add EU nuts codes")


@cli.callback(invoke_without_command=True)
def cli_store(
    version: Annotated[Optional[bool], typer.Option(..., help="Show version")] = False,
):
    if version:
        print(__version__)
        raise typer.Exit()
    configure_logging()


@cli.command()
def config():
    """Show current configuration"""
    with ErrorHandler():
        console.print(settings)


@cli.command()
def format_line(
    input_uri: str = Opts.IN,
    input_format: IOFormats = Opts.IOFORMATS,
    output_uri: str = Opts.OUT,
    output_format: IOFormats = Opts.IOFORMATS,
):
    """
    Get formatted lines via libpostal parsing from csv or json input stream with
    1 or more fields:
        - "original_line": address line
        - "country" (optional): country or iso code - good to know for libpostal
        - "language" (optional): language or iso code - good to know for libpostal
        - all other columns will be passed through to the result

    Example:
        ftmgeo format-line -i addresses.csv --input-format csv -o s3://my_bucket/addresses.json
    """
    with ErrorHandler():
        if not settings.libpostal:
            raise Exception("Please install and activate libpostal")
        with ModelWriter(output_uri, output_format=output_format) as writer:
            for row in smart_stream_models(input_uri, PostalRow, input_format):
                row = logic.format_line(row)
                writer.write(row)


@cli.command()
def parse_components(
    input_uri: str = Opts.IN,
    input_format: IOFormats = Opts.IOFORMATS,
    output_uri: str = Opts.OUT,
    output_format: IOFormats = Opts.IOFORMATS,
):
    """
    Get components parsed from libpostal from csv or json input stream with 1 or
    more fields:
        - "original_line": address line
        - "country" (optional): country or iso code - good to know for libpostal
        - "language" (optional): language or iso code - good to know for libpostal
        - all other columns will be passed through to the result

    Example:
        cat data.json | ftmgeo parse-components --output-format csv > data.csv
    """
    with ErrorHandler():
        if not settings.libpostal:
            raise Exception("Please install and activate libpostal")
        rows = smart_stream_models(input_uri, PostalRow, input_format)
        row = next(rows)
        keys = row.model_dump().keys()
        fieldnames = list(set(keys) | set(POSTAL_KEYS))
        with Writer(
            output_uri, output_format=output_format, fieldnames=fieldnames
        ) as writer:
            row = logic.parse_components(row)
            writer.write(row)
            for row in rows:
                row = logic.parse_components(row)
                writer.write(row)


@cli.command()
def map_entities(
    input_uri: str = Opts.IN,
    input_format: IOFormats = Opts.IOFORMATS,
    output_uri: str = Opts.OUT,
):
    """
    Map csv/json input stream to FollowTheMoney Address proxies, requires
    libpostal

    Required input field: `original_line`
    """
    with ErrorHandler():
        if not settings.libpostal:
            raise Exception("Please install and activate libpostal")
        rows = smart_stream_models(input_uri, PostalRow, input_format)
        addresses = (
            get_address(
                r.original_line,
                country=r.country,
                language=r.language,
            )
            for r in rows
        )
        proxies = (a.to_proxy() for a in addresses)
        smart_write_proxies(output_uri, proxies)


@cli.command()
def geocode(
    input_uri: str = Opts.IN,
    input_format: Formats = Opts.FORMATS,
    output_uri: str = Opts.OUT,
    output_format: Formats = Opts.FORMATS,
    geocoders: list[GEOCODERS] = Opts.GEOCODERS,
    use_cache: Annotated[bool, typer.Option(help="Use cache database")] = True,
    cache_only: Annotated[bool, typer.Option(help="Only use cache database")] = False,
    rewrite_ids: Annotated[
        bool, typer.Option(help="Rewrite `Address` entity ids to canonized id")
    ] = True,
    apply_nuts: Annotated[bool, typer.Option(help="Add EU nuts codes")] = False,
):
    """
    Geocode ftm entities or csv input to given output format using different
    geocoders. When using csv input, these columns must be used:

    Columns:
        - "original_line": address line
        - "country" (optional): country or iso code - good to know for libpostal
        - "language" (optional): language or iso code - good to know for libpostal
        - all other columns will be passed through to the result

    Example:
        ftmgeo geocode -i s3://my_bucket/entities.ftm.json > entities.geocoded.ftm.json
    """
    with ErrorHandler():
        if input_format == Formats.ftm:
            proxies = smart_read_proxies(input_uri)
            results = (
                geocode_proxy(
                    geocoders,
                    p,
                    use_cache=use_cache,
                    cache_only=cache_only,
                    apply_nuts=apply_nuts,
                    output_format=output_format,
                    rewrite_ids=rewrite_ids,
                )
                for p in proxies
            )
            results = (p for res in results for p in res)
        else:
            tasks = smart_stream_models(input_uri, PostalRow, input_format)
            results = (
                geocode_line(
                    geocoders,
                    t.original_line,
                    use_cache=use_cache,
                    cache_only=cache_only,
                    country=t.country,
                    apply_nuts=apply_nuts,
                )
                for t in tasks
            )
        out_format = FORMAT_CSV if output_format == FORMAT_CSV else FORMAT_JSON
        with Writer(output_uri, output_format=out_format) as writer:
            for res in results:
                if res is not None:
                    if output_format == FORMAT_FTM:
                        if input_format != FORMAT_FTM:
                            res = res.to_proxy()
                        res = res.to_dict()
                    else:
                        res = res.model_dump(mode="json")
                writer.write(res)


@cli.command()
def apply_nuts(
    input_uri: str = Opts.IN,
    input_format: Formats = Opts.FORMATS,
    output_uri: str = Opts.OUT,
    output_format: IOFormats = Opts.IOFORMATS,
):
    """
    Apply EU NUTS codes to input stream

    For ftm input, only Address entities with longitude and latitude properties
    will be considered.

    For csv or json input, use these fields:
        - "lat": Latitude
        - "lon": Longitude
        - all other fields will be passed through to the result
    """
    with ErrorHandler():
        if input_format == FORMAT_FTM:
            with ModelWriter(output_uri, output_format=output_format) as writer:
                for proxy in smart_read_proxies(input_uri):
                    nuts = get_proxy_nuts(proxy)
                    if nuts is not None:
                        writer.write(nuts)
        else:
            with Writer(output_uri, output_format=output_format) as writer:
                for row in smart_stream_models(input_uri, LatLonRow, input_format):
                    nuts = get_nuts(row.lon, row.lat)
                    if nuts is not None:
                        data = row.model_dump()
                        data.update(nuts.model_dump())
                        writer.write(data)


@cli_cache.command("iterate")
def cache_iterate(
    output_uri: str = Opts.OUT,
    output_format: Formats = Opts.FORMATS,
    apply_nuts: bool = Opts.APPLY_NUTS,
):
    """
    Export cached addresses to csv or ftm entities
    """
    with ErrorHandler():
        cache = get_cache()
        results = cache.iterate_values()
        if apply_nuts:
            results = (r.apply_nuts() for r in results)
        if output_format in (FORMAT_CSV, FORMAT_JSON):
            with ModelWriter(output_uri, output_format=output_format) as writer:
                for res in results:
                    writer.write(res)
        else:
            proxies = (r.to_proxy() for r in results)
            smart_write_proxies(output_uri, proxies)


@cli_cache.command("populate")
def cache_populate(
    input_uri: str = Opts.IN,
    input_format: IOFormats = Opts.IOFORMATS,
    apply_nuts: bool = Opts.APPLY_NUTS,
):
    """
    Populate cache from csv or json input with these fields:\n
        address_id: str\n
        canonical_id: str\n
        original_line: str\n
        result_line: str\n
        country: str\n
        lat: float\n
        lon: float\n
        geocoder: str\n
        geocoder_place_id: str | None = None\n
        geocoder_raw: str | None = None\n
        nuts0_id: str | None = None\n
        nuts1_id: str | None = None\n
        nuts2_id: str | None = None\n
        nuts3_id: str | None = None\n
        ts: datetime | None = None\n
    """
    with ErrorHandler():
        cache = get_cache()
        for row in smart_stream_models(input_uri, GeocodingResult, input_format):
            if apply_nuts:
                row.apply_nuts()
            cache.put(row.address_id, row)
