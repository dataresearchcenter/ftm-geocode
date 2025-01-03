from typing import Optional

import typer
from anystore.cli import ErrorHandler
from ftmq.io import smart_read_proxies, smart_write_proxies
from rich.console import Console
from typing_extensions import Annotated

from ftm_geocode import __version__
from ftm_geocode.cache import get_cache
from ftm_geocode.geocode import GEOCODERS
from ftm_geocode.io import (
    Formats,
    Writer,
    read_geocode_results_csv,
    read_latlon_csv,
    read_postal_csv,
    write_geocode_results,
)
from ftm_geocode.logging import configure_logging, get_logger
from ftm_geocode.settings import Settings
from ftm_geocode.worker import (
    ApplyNutsWorker,
    CachePopulateWorker,
    FormatLineWorker,
    GeocodeWorker,
    ParseComponentsWorker,
)

settings = Settings()
cli = typer.Typer(no_args_is_help=True)
cli_cache = typer.Typer()
cli.add_typer(cli_cache, name="cache")
console = Console(stderr=True)

log = get_logger(__name__)


class Opts:
    IN = typer.Option("-", "-i", help="Input uri (file, http, s3...)")
    OUT = typer.Option("-", "-o", help="Output uri (file, http, s3...)")
    FORMATS = typer.Option(Formats.ftm)
    GEOCODERS = typer.Option(settings.geocoders, "--geocoder", "-g")
    APPLY_NUTS = typer.Option(False, help="Add EU nuts codes")
    ENSURE_IDS = typer.Option(
        False,
        help="Make sure address IDs are in most recent format (useful for migrating)",
    )


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
def format_line(input_uri: str = Opts.IN, output_uri: str = Opts.OUT):
    """
    Get formatted lines via libpostal parsing from csv input stream with 1 or
    more columns:
        - "original_line": address line
        - "country" (optional): country or iso code - good to know for libpostal
        - "language" (optional): language or iso code - good to know for libpostal
        - all other columns will be passed through to the result
    """
    with ErrorHandler():
        if not settings.libpostal:
            raise Exception("Please install and activate libpostal")
        worker = FormatLineWorker(
            writer=Writer(output_uri), tasks=read_postal_csv(input_uri)
        )
        res = worker.run()
        console.print(res)


@cli.command()
def parse_components(input_uri: str = Opts.IN, output_uri: str = Opts.OUT):
    """
    Get components parsed from libpostal from csv input stream with 1 or
    more columns:
        - "original_line": address line
        - "country" (optional): country or iso code - good to know for libpostal
        - "language" (optional): language or iso code - good to know for libpostal
        - all other columns will be passed through to the result
    """
    with ErrorHandler():
        if not settings.libpostal:
            raise Exception("Please install and activate libpostal")
        worker = ParseComponentsWorker(
            writer=Writer(output_uri), tasks=read_postal_csv(input_uri)
        )
        res = worker.run()
        console.print(res)


@cli.command()
def geocode(
    input_uri: str = Opts.IN,
    input_format: Formats = Opts.FORMATS,
    output_uri: str = Opts.OUT,
    output_format: Formats = Opts.FORMATS,
    geocoder: list[GEOCODERS] = Opts.GEOCODERS,
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

    """
    with ErrorHandler():
        if input_format == Formats.ftm:
            tasks = smart_read_proxies(input_uri)
        else:
            tasks = read_postal_csv(input_uri)
        writer = Writer(output_uri, output_format=output_format)
        worker = GeocodeWorker(
            writer=writer,
            tasks=tasks,
            use_cache=use_cache,
            cache_only=cache_only,
            geocoder=geocoder,
            input_format=input_format,
            output_format=output_format,
            rewrite_ids=rewrite_ids,
            apply_nuts=apply_nuts,
        )
        res = worker.run()
        console.print(res)


@cli.command()
def apply_nuts(
    input_uri: str = Opts.IN,
    input_format: Formats = Opts.FORMATS,
    output_uri: str = Opts.OUT,
    output_format: Formats = Opts.FORMATS,
):
    """
    Apply EU NUTS codes to input stream

    For ftm input, only Address entities with longitude and latitude properties
    well be considered.

    For csv input, use these columns:
        - "lat": Latitude
        - "lon": Longitude
        - all other columns will be passed through to the result
    """
    with ErrorHandler():
        if input_format == Formats.ftm:
            tasks = smart_read_proxies(input_uri)
        else:
            tasks = read_latlon_csv(input_uri)
        writer = Writer(output_uri, output_format=output_format)
        worker = ApplyNutsWorker(
            tasks=tasks,
            writer=writer,
            input_format=input_format,
            output_format=output_format,
        )
        res = worker.run()
        console.print(res)


@cli_cache.command("iterate")
def cache_iterate(
    output_uri: str = Opts.OUT,
    output_format: Formats = Opts.FORMATS,
    apply_nuts: bool = Opts.APPLY_NUTS,
    ensure_ids: bool = Opts.ENSURE_IDS,
):
    """
    Export cached addresses to csv or ftm entities
    """
    with ErrorHandler():
        cache = get_cache()
        results = cache.iterate_values(prefix=settings.cache_prefix)
        if ensure_ids:
            results = (r.ensure_canonical_id() for r in results)
        if apply_nuts:
            results = (r.apply_nuts() for r in results)
        if output_format == Formats.csv:
            write_geocode_results(output_uri, results)
        else:
            proxies = (r.to_proxy() for r in results)
            smart_write_proxies(output_uri, proxies, serialize=True)


@cli_cache.command("populate")
def cache_populate(
    input_uri: str = Opts.IN,
    apply_nuts: bool = Opts.APPLY_NUTS,
    ensure_ids: bool = Opts.ENSURE_IDS,
):
    """
    Populate cache from csv input with these columns:\n
        cache_key: str | None = None\n
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
        nuts3_id: str | None = None
        ts: datetime | None = None
    """
    with ErrorHandler():
        worker = CachePopulateWorker(
            tasks=read_geocode_results_csv(input_uri),
            apply_nuts=apply_nuts,
            ensure_ids=ensure_ids,
        )
        res = worker.run()
        console.print(res)
