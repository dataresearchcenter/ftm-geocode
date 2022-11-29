# ftm-geocoder

Batch parse and geocode addresses from
[followthemoney entities](https://followthemoney.readthedocs.io/en/latest/).
Simply geocoding just address strings works as well, of course.

There are as well some parsing / normalization helpers.

## Features
- Parse/normalize addresses via [libpostal](https://github.com/openvenues/libpostal)
- Geocoding via [geopy](https://geopy.readthedocs.io/en/stable/)
- Cache geocoding results in a sql database (using [dataset](https://github.com/pudo/dataset))
- Optional fallback geocoders when preferred geocoder doesn't match
- Create, update and merge [`Address`](https://followthemoney.readthedocs.io/en/latest/model.html#address) entities for ftm data

## Usage

### command line

    ftmgeo --help

The command line interface is designed for piping input / output streams, but
for each command a `-i <input_file>` and `-o <output_file>` can be used as well.

Geocode an input stream of ftm entities with nominatim and google maps as
fallback (geocoders are tried in the given order):

    cat entitis.ftm.ijson | ftmgeo geocode -g nominatim -g google > entities_geocoded.ftm.ijson

This looks for the [address prop](https://followthemoney.readthedocs.io/en/latest/types.html#type-address)
on input entities and creates address entities with reference to the input
entities. The output contains all entities from the input stream plus newly
created addresses.

If an input entity is itself an [Address entity](https://followthemoney.readthedocs.io/en/latest/model.html#address),
it will be geocoded as well and their props (country, city, ...) will be merged
with the geocoder result.

During the process, addresses are parsed and normalized and looked up in the
address cache database before actual geocoding. After geocoding, new addresses
are added to the cache database.

Address ids will be rewritten based on normalization (`addressEntity` refs are updated on other entities),
to keep the original ids, add the flag `--no-rewrite-ids`

Geocoders can be set via `GEOCODERS` and default to `nominatim`

More information:

    ftmgeo geocode --help

### geocoding just address strings

**csv format (for all csv input streams)**
first column `address`, optional second column `country` (name or code) and
third `language` for postal context

To ftm address entities:

    cat addresses.csv | ftmgeo geocode --input-format=csv > addresses.ftm.ijson

To csv:

    cat addresses.csv | ftmgeo geocode --input-format=csv --output-format=csv > addresses.csv

### formatting / normalization

    cat addresses.txt | ftmgeo format-line > clean_addresses.csv

Generate address entities (without geocoding):

    cat entities.ftm.ijson | ftmgeo map > entities.ftm.ijson
    cat addresses.csv | ftmgeo map --input-format=csv > addresses.ftm.ijson

### database cache

    ftmgeo cache --help

During geocoding, addresses are first looked up in the local cache, and new
geocoding results are added.

Ignore cache during geocoding (new results are still written to it):

    ftmgeo geocode --no-cache ...

Export cache:

    ftmgeo cache iterate > geocoded_addresses.ftm.ijsonl
    ftmgeo cache iterate --output-format=csv > geocoded_addresses.csv

Populate cache:

*csv input:*
`address_id,canonical_id,original_line,result_line,country,lat,lon,geocoder,geocoder_place_id`

optional field: `geocoder_raw` - json of geocoder response

    cat geocoded_addresses.csv | ftmgeo cache populate

### apply cache / re-geocode

    ftmgeo cache apply-csv --help

To get addresses from cache without geocoding from a csv input stream, passing
through additional csv data from input:

    cat addresses.csv | ftmgeo cache apply-csv --output-format csv > results.csv

Only get missing to re-geocode (e.g. with a different geocoder):

    cat addresses.csv | ftmgeo cache apply-csv --output-format csv --get-missing | ftmgeo geocode

## Configuration

**geocoders**

Default geocoders: env var `GEOCODERS`
They are used in the given order

Make sure to configure the geocoders as needed for `geopy` (endpoints, api keys, ...):

`export FTMGEO_<GEOCODERNAME>_<SETTING>=...`

**Persistent cache**

The cache database is set via `FTM_STORE_URI` (so it is the same as the
[ftm store](https://github.com/alephdata/followthemoney-store), if any,
otherwise it defaults to `sqlite:///cache.db`

## Installation

Required external is [libpostal](https://github.com/openvenues/pypostal), see installation instructions there.

Once `libpostal` is installed on your system, you can install:

    pip install ftm-geocoder

Verify that this works without errors:

    ftmgeo --help

    echo "Cowley Road, Cambridge, UK" | ftmgeo geocode --input-format=csv --no-header

## Testing

    make install
    make test
