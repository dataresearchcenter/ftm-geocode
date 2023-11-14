import csv
from datetime import datetime

import typer
from typing_extensions import Annotated

from ftm_geocode.cache import get_cache
from ftm_geocode.geocode import GEOCODERS, geocode_line, geocode_proxy
from ftm_geocode.io import Formats, get_coords_reader, get_reader, get_writer
from ftm_geocode.logging import configure_logging, get_logger
from ftm_geocode.model import POSTAL_KEYS, GeocodingResult, get_address, get_components
from ftm_geocode.nuts import Nuts3, get_proxy_nuts
from ftm_geocode.settings import LOG_LEVEL

cli = typer.Typer()
cli_cache = typer.Typer()
cli.add_typer(cli_cache, name="cache")

configure_logging(LOG_LEVEL)

log = get_logger(__name__)


class Opts:
    IN = Annotated[str, typer.Option("-", "-i", help="Input uri (file, http, s3...)")]
    OUT = Annotated[str, typer.Option("-", "-o", help="Output uri (file, http, s3...)")]
    HEADER = Annotated[bool, typer.Option(True, help="Input csv stream has header row")]
    FORMATS = Annotated[Formats, typer.Option(Formats.ftm.value)]
    GEOCODERS = Annotated[
        list[GEOCODERS], typer.Option([GEOCODERS.nominatim.value], "--geocoder", "-g")
    ]
    RAW = Annotated[
        bool,
        typer.Option(False, help="Include geocoder raw response (for csv output only)"),
    ]
    APPLY_NUTS = Annotated[bool, typer.Option(False, help="Add EU nuts codes")]
    ENSURE_IDS = Annotated[
        bool,
        typer.Option(
            False,
            help="Make sure address IDs are in most recent format (useful for migrating)",
        ),
    ]


@cli.command()
def format_line(input_file: Opts.IN, output_file: Opts.OUT, header: Opts.HEADER):
    """
    Get formatted line via libpostal parsing from csv input stream with 1 or
    more columns:\n
        - 1st column: address line\n
        - 2nd column (optional): country or iso code - good to know for libpostal\n
        - 3rd column (optional): language or iso code - good to know for libpostal\n
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
def parse_components(input_file: Opts.IN, output_file: Opts.OUT, header: Opts.HEADER):
    """
    Get components parsed from libpostal from csv input stream with 1 or
    more columns:\n
        - 1st column: address line\n
        - 2nd column (optional): country or iso code - good to know for libpostal\n
        - 3rd column (optional): language or iso code - good to know for libpostal\n
        - all other columns will be passed through and appended to the result\n
          (if using extra columns, country and language columns needs to be present)\n
    """
    reader = get_reader(input_file, Formats.csv, header=header)
    writer = csv.DictWriter(
        output_file,
        fieldnames=["original_line", *POSTAL_KEYS, "language"],
    )
    writer.writeheader()

    for original_line, country, language, *_rest in reader:
        data = get_components(original_line, country=country, language=language)
        data.update(original_line=original_line, language=language, country=country)
        writer.writerow(data)


@cli.command()
def geocode(
    input_file: Opts.IN,
    input_format: Opts.FORMATS,
    output_file: Opts.OUT,
    output_format: Opts.FORMATS,
    geocoder: Opts.GEOCODERS,
    include_raw: Opts.RAW,
    header: Opts.HEADER,
    cache: Annotated[bool, typer.Option(..., help="Use cache database")] = True,
    rewrite_ids: Annotated[
        bool, typer.Option(..., help="Rewrite `Address` entity ids to canonized id")
    ] = True,
    apply_nuts: Annotated[bool, typer.Option(..., help="Add EU nuts codes")] = False,
    verbose_log: Annotated[
        bool, typer.Option(..., help="Don't log cache hits")
    ] = False,
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
        for address, country, _language, *rest in reader:
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
    input_file: Opts.IN,
    input_format: Opts.FORMATS,
    output_file: Opts.OUT,
    header: Opts.HEADER,
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
    output_file: Opts.OUT,
    output_format: Opts.FORMATS,
    include_raw: Opts.RAW,
    apply_nuts: Opts.APPLY_NUTS,
    ensure_ids: Opts.ENSURE_IDS,
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
    input_file: Opts.IN,
    apply_nuts: Opts.APPLY_NUTS,
    ensure_ids: Opts.ENSURE_IDS,
):
    """
    Populate cache from csv input with these columns:\n
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
    input_file: Opts.IN,
    output_file: Opts.OUT,
    output_format: Opts.FORMATS,
    include_raw: Opts.RAW,
    address_column: Annotated[
        str, typer.Option("address", help="Column name for address line")
    ],
    country_column: Annotated[
        str, typer.Option("country", help="Column name for country")
    ],
    language_column: Annotated[
        str, typer.Option("language", help="Column name for language")
    ],
    get_missing: Annotated[
        bool, typer.Option(False, help="Only output unmatched address data.")
    ],
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
