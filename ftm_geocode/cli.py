import csv
from datetime import datetime

import typer

from .cache import cache
from .geocode import Geocoders, geocode_line, geocode_proxy
from .io import Formats, get_reader, get_writer
from .model import GeocodingResult, get_address

cli = typer.Typer()
cli_cache = typer.Typer()
cli.add_typer(cli_cache, name="cache")


@cli.command()
def format_line(
    input_file: typer.FileText = typer.Option("-", "-i", help="input file"),
    output_file: typer.FileTextWrite = typer.Option("-", "-o", help="output file"),
    header: bool = typer.Option(True, help="Input stream has csv header row"),
):
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
    writer = get_writer(output_file, output_format, include_raw=include_raw)

    for res in cache.iterate():
        writer(res)


@cli_cache.command("populate")
def cache_populate(
    input_file: typer.FileText = typer.Option("-", "-i", help="Input file"),
    input_format: Formats = typer.Option(Formats.csv.value, help="Input format"),
):
    reader = csv.DictReader(input_file)
    bulk = cache.bulk()

    for row in reader:
        if "ts" not in row:
            row["ts"] = datetime.now()
        result = GeocodingResult(**row)
        bulk.put(result)
    bulk.flush()
