The command line interface is designed for piping input / output streams, but
for each command a `-i <input_file>` and `-o <output_file>` can be used as well.

Geocode an input stream of ftm entities with nominatim and google maps as
fallback (geocoders are tried in the given order):

    cat entities.ftm.ijson | ftmgeo geocode -g nominatim -g google > entities_geocoded.ftm.ijson

This looks for the [address prop](https://followthemoney.tech/explorer/types/address/) on input entities and creates address entities with reference to the input entities. The output contains all entities from the input stream plus newly created address entities.

If an input entity is itself an address entity, it will be geocoded as well and their props (country, city, ...) will be merged with the geocoder result.

During the process, addresses are parsed and normalized and looked up in the
address cache database before actual geocoding. After geocoding, new addresses
are added to the cache database.

Address ids can be rewritten based on normalization (`addressEntity` refs are updated on other entities),
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

Get a cleaned address line from messy input strings.

    cat addresses.txt | ftmgeo format-line > clean_addresses.csv

### libpostal parsed components

Get a csv with all the parsed components from libpostal.

    cat addresses.txt | ftmgeo parse-components > components.csv

### mapping

Generate address entities from input stream (without geocoding):

    cat entities.ftm.ijson | ftmgeo map > entities.ftm.ijson
    cat addresses.csv | ftmgeo map --input-format=csv > addresses.ftm.ijson
