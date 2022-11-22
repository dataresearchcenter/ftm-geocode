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
):
    reader = get_reader(input_file, Formats.csv)
    writer = get_writer(output_file, Formats.csv)

    for address, country, language, *rest in reader:
        address = get_address(address, language=language, country=country)
        writer([address.get_formatted_line(), ";".join(address.country), *rest])


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
):
    reader = get_reader(input_file, input_format)
    writer = get_writer(output_file, output_format)

    if input_format == Formats.ftm:
        for proxy in reader:
            for result in geocode_proxy(
                geocoder, proxy, use_cache=cache, output_format=output_format
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
):
    writer = get_writer(output_file, output_format)

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
