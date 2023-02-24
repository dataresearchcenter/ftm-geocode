import csv
from datetime import datetime

import typer

from .cache import get_cache
from .geocode import GEOCODERS, geocode_line, geocode_proxy
from .io import Formats, get_coords_reader, get_reader, get_writer
from .logging import configure_logging, get_logger
from .model import POSTAL_KEYS, GeocodingResult, get_address, get_components
from .nuts import Nuts3, get_proxy_nuts
from .settings import LOG_LEVEL

cli = typer.Typer()
cli_cache = typer.Typer()
cli.add_typer(cli_cache, name="cache")

configure_logging(LOG_LEVEL)

log = get_logger(__name__)


@cli.command()
def format_line(
    input_file: typer.FileText = typer.Option("-", "-i", help="input file"),
    output_file: typer.FileTextWrite = typer.Option("-", "-o", help="output file"),
    header: bool = typer.Option(True, help="Input stream has csv header row"),
):
    """
    Get formatted line via libpostal parsing from csv input stream with 1 or
    more columns:\n
        - 1st column: address line\n
        - 2nd column (optional): country or iso code - good to know for libpostal\n
        - 3nd column (optional): language or iso code - good to know for libpostal\n
        - all other columns will be passed through and appended to the result\n
          (if using extra columns, country and language columns needs to be present)\n
    """
    reader = get_reader(input_file, Formats.csv, header=header)
    writer = csv.writer(output_file)

    for address, country, language, *rest in reader:
        address = get_address(address, language=language, country=country)
        writer.writerow(
            [address.get_formatted_line(), ";".join(address.country), *rest]
        )


@cli.command()
def parse_components(
    input_file: typer.FileText = typer.Option("-", "-i", help="input file"),
    output_file: typer.FileTextWrite = typer.Option("-", "-o", help="output file"),
    header: bool = typer.Option(True, help="Input stream has csv header row"),
):
    """
    Get components parsed from libpostal from csv input stream with 1 or
    more columns:\n
        - 1st column: address line\n
        - 2nd column (optional): country or iso code - good to know for libpostal\n
        - 3nd column (optional): language or iso code - good to know for libpostal\n
        - all other columns will be passed through and appended to the result\n
          (if using extra columns, country and language columns needs to be present)\n
    """
    reader = get_reader(input_file, Formats.csv, header=header)
    writer = csv.DictWriter(
        output_file,
        fieldnames=["original_line", *POSTAL_KEYS, "language"],
    )
    writer.writeheader()

    for original_line, country, language, *rest in reader:
        data = get_components(original_line, country=country, language=language)
        data.update(original_line=original_line, language=language, country=country)
        writer.writerow(data)


@cli.command()
def geocode(
    input_file: typer.FileText = typer.Option("-", "-i", help="Input file"),
    input_format: Formats = typer.Option(Formats.ftm.value, help="Input format"),
    output_file: typer.FileTextWrite = typer.Option("-", "-o", help="Output file"),
    output_format: Formats = typer.Option(Formats.ftm.value, help="Output format"),
    geocoder: list[GEOCODERS] = typer.Option(
        [GEOCODERS.nominatim.value], "--geocoder", "-g"
    ),
    cache: bool = typer.Option(True, help="Use cache database"),
    include_raw: bool = typer.Option(
        False, help="Include geocoder raw response (for csv output only)"
    ),
    rewrite_ids: bool = typer.Option(
        True, help="Rewrite `Address` entity ids to canonized id"
    ),
    header: bool = typer.Option(True, help="Input stream has csv header row"),
    apply_nuts: bool = typer.Option(False, help="Add EU nuts codes"),
    verbose_log: bool = typer.Option(False, help="Don't log cache hits"),
):
    """
    Geocode ftm entities or csv input to given output format using different geocoders
    """
    reader = get_reader(input_file, input_format, header=header)
    writer = get_writer(output_file, output_format, include_raw=include_raw)

    if input_format == Formats.ftm:
        for proxy in reader:
            for result in geocode_proxy(
                geocoder,
                proxy,
                use_cache=cache,
                output_format=output_format,
                rewrite_ids=rewrite_ids,
                apply_nuts=apply_nuts,
                verbose_log=verbose_log,
            ):
                writer(result)

    else:
        for address, country, language, *rest in reader:
            result = geocode_line(
                geocoder,
                address,
                use_cache=cache,
                country=country,
                apply_nuts=apply_nuts,
                verbose_log=verbose_log,
            )
            if result is not None:
                writer(result, *rest)


@cli.command()
def apply_nuts(
    input_file: typer.FileText = typer.Option("-", "-i", help="Input file"),
    input_format: Formats = typer.Option(Formats.ftm.value, help="Input format"),
    output_file: typer.FileTextWrite = typer.Option("-", "-o", help="Output file"),
    header: bool = typer.Option(True, help="Input stream has csv header row"),
):
    """
    Apply EU NUTS codes to input stream (outputs always csv)
    """
    reader = get_coords_reader(input_file, input_format, header=header)

    if input_format == Formats.ftm:
        writer = csv.DictWriter(
            output_file, fieldnames=["id", *Nuts3.__fields__.keys()]
        )
        writer.writeheader()
        ix = 0
        for ix, proxy in enumerate(reader):
            nuts = get_proxy_nuts(proxy)
            if nuts is not None:
                writer.writerow({**{"id": proxy.id}, **nuts.dict()})
            if ix and ix % 1_000 == 0:
                log.info("Parse proxy %d ..." % ix)
        if ix:
            log.info("Parsed %d proxies" % (ix + 1))

    if input_format == Formats.csv:
        raise NotImplementedError("currently only ftm input stream implemented")


@cli_cache.command("iterate")
def cache_iterate(
    output_file: typer.FileTextWrite = typer.Option("-", "-o", help="Output file"),
    output_format: Formats = typer.Option(Formats.ftm.value, help="Output format"),
    include_raw: bool = typer.Option(False, help="Include geocoder raw response"),
    apply_nuts: bool = typer.Option(False, help="Add EU nuts codes"),
    ensure_ids: bool = typer.Option(
        False,
        help="Make sure address IDs are in most recent format (useful for migrating)",
    ),
):
    """
    Export cached addresses to csv or ftm entities
    """
    writer = get_writer(output_file, output_format, include_raw=include_raw)
    cache = get_cache()

    for res in cache.iterate():
        if output_format == Formats.csv and apply_nuts:
            res.apply_nuts()
        if ensure_ids:
            res.ensure_canonical_id()
        writer(res)


@cli_cache.command("populate")
def cache_populate(
    input_file: typer.FileText = typer.Option("-", "-i", help="Input file"),
    apply_nuts: bool = typer.Option(False, help="Add EU nuts codes"),
    ensure_ids: bool = typer.Option(
        False,
        help="Make sure address IDs are in most recent format (useful for migrating)",
    ),
):
    """
    Populate cache from csv input with these columns:
        address_id: str
        canonical_id: str
        original_line: str
        result_line: str
        country: str
        lat: float
        lon: float
        geocoder: str
        geocoder_place_id: str | None = None
        geocoder_raw: str | None = None
        nuts0_id: str | None = None
        nuts1_id: str | None = None
        nuts2_id: str | None = None
        nuts3_id: str | None = None
    """
    reader = csv.DictReader(input_file)
    cache = get_cache()
    bulk = cache.bulk()

    for row in reader:
        if "ts" not in row:
            row["ts"] = datetime.now()
        result = GeocodingResult(**row)
        if apply_nuts:
            result.apply_nuts()
        if ensure_ids:
            result.ensure_canonical_id()
        bulk.put(result)
    bulk.flush()


@cli_cache.command("apply-csv")
def cache_apply_csv(
    input_file: typer.FileText = typer.Option("-", "-i", help="Input file"),
    output_file: typer.FileTextWrite = typer.Option("-", "-o", help="Output file"),
    output_format: Formats = typer.Option(Formats.ftm.value, help="Output format"),
    include_raw: bool = typer.Option(False, help="Include geocoder raw response"),
    address_column: str = typer.Option("address", help="Column name for address line"),
    country_column: str = typer.Option("country", help="Column name for country"),
    language_column: str = typer.Option("language", help="Column name for language"),
    get_missing: bool = typer.Option(False, help="Only output unmatched address data."),
):
    """
    Apply geocoding results from cache only ("dry" geocoding) to a csv input stream

    If input is csv, it needs a header row to pass through extra fields
    """
    reader = csv.DictReader(input_file)
    writer = get_writer(
        output_file,
        output_format,
        include_raw=include_raw,
        extra_fields=reader.fieldnames,
    )
    cache = get_cache()

    for row in reader:
        address = row.get(address_column)
        country = row.get(country_column, "")
        language = row.get(language_column, "")
        if address is not None:
            result = cache.get(address, country=country, language=language)
            if result is not None:
                log.info(f"Cache hit: `{address}`", cache=str(cache), country=country)
                if not get_missing:
                    writer(result, extra_data=row)
            else:
                log.warning(f"No cache for `{address}`", country=country)
                if get_missing:
                    writer(extra_data=row)
