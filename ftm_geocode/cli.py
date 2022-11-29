import csv
from datetime import datetime

import typer

from .cache import cache
from .geocode import Geocoders, geocode_line, geocode_proxy
from .io import Formats, get_reader, get_writer
from .logging import get_logger
from .model import GeocodingResult, get_address

cli = typer.Typer()
cli_cache = typer.Typer()
cli.add_typer(cli_cache, name="cache")

log = get_logger(__name__)


@cli.command()
def format_line(
    input_file: typer.FileText = typer.Option("-", "-i", help="input file"),
    output_file: typer.FileTextWrite = typer.Option("-", "-o", help="output file"),
    header: bool = typer.Option(True, help="Input stream has csv header row"),
):
    """
    Get formatted line via libpostal parsing from csv input stream with 1 or
    more columns:
        - 1st column: address line
        - 2nd column (optional): country or iso code - good to know for libpostal
        - 3nd column (optional): language or iso code - good to know for libpostal
        - all other columns will be passed through and appended to the result
          (if using extra columns, country and language columns needs to be present)
    """
    reader = get_reader(input_file, Formats.csv, header=header)
    writer = csv.writer(output_file)

    for address, country, language, *rest in reader:
        address = get_address(address, language=language, country=country)
        writer.writerow(
            [address.get_formatted_line(), ";".join(address.country), *rest]
        )


@cli.command()
def geocode(
    input_file: typer.FileText = typer.Option("-", "-i", help="Input file"),
    input_format: Formats = typer.Option(Formats.ftm.value, help="Input format"),
    output_file: typer.FileTextWrite = typer.Option("-", "-o", help="Output file"),
    output_format: Formats = typer.Option(Formats.ftm.value, help="Output format"),
    geocoder: list[Geocoders] = typer.Option(
        [Geocoders.nominatim.value], "--geocoder", "-g"
    ),
    cache: bool = typer.Option(True, help="Use cache database"),
    include_raw: bool = typer.Option(
        False, help="Include geocoder raw response (for csv output only)"
    ),
    rewrite_ids: bool = typer.Option(
        True, help="Rewrite `Address` entity ids to canonized id"
    ),
    header: bool = typer.Option(True, help="Input stream has csv header row"),
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
            ):
                writer(result)

    else:
        for address, country, language, *rest in reader:
            result = geocode_line(geocoder, address, use_cache=cache, country=country)
            if result is not None:
                writer(result, *rest)


@cli_cache.command("iterate")
def cache_iterate(
    output_file: typer.FileTextWrite = typer.Option("-", "-o", help="Output file"),
    output_format: Formats = typer.Option(Formats.ftm.value, help="Output format"),
    include_raw: bool = typer.Option(False, help="Include geocoder raw response"),
):
    """
    Export cached addresses to csv or ftm entities
    """
    writer = get_writer(output_file, output_format, include_raw=include_raw)

    for res in cache.iterate():
        writer(res)


@cli_cache.command("populate")
def cache_populate(
    input_file: typer.FileText = typer.Option("-", "-i", help="Input file"),
    input_format: Formats = typer.Option(Formats.csv.value, help="Input format"),
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
    """
    reader = csv.DictReader(input_file)
    bulk = cache.bulk()

    for row in reader:
        if "ts" not in row:
            row["ts"] = datetime.now()
        result = GeocodingResult(**row)
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
