[![ftm-geocode on pypi](https://img.shields.io/pypi/v/ftm-geocode)](https://pypi.org/project/ftm-geocode/)
[![Python test and package](https://github.com/investigativedata/ftm-geocode/actions/workflows/python.yml/badge.svg)](https://github.com/investigativedata/ftm-geocode/actions/workflows/python.yml)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Coverage Status](https://coveralls.io/repos/github/investigativedata/ftm-geocode/badge.svg?branch=main)](https://coveralls.io/github/investigativedata/ftm-geocode?branch=main)
[![AGPL-3.0 License](https://img.shields.io/pypi/l/ftm-geocode)](./LICENSE)

# ftm-geocode

Batch parse and geocode addresses from
[followthemoney entities](https://followthemoney.readthedocs.io/en/latest/).
Simply geocoding just address strings works as well, of course.

There are as well some parsing / normalization helpers.

## Features
- Parse/normalize addresses via [libpostal](https://github.com/openvenues/libpostal)
- Geocoding via [geopy](https://geopy.readthedocs.io/en/stable/)
- Cache geocoding results using [anystore](https://docs.investigraph.dev/lib/anystore)
- Optional fallback geocoders when preferred geocoder doesn't match
- Create, update and merge [`Address`](https://followthemoney.readthedocs.io/en/latest/model.html#address) entities for ftm data

## Quickstart

    pip install ftm-geocode

Geocode an input stream of ftm entities with nominatim and google maps as fallback (geocoders are tried in the given order):

    cat entities.ftm.ijson | ftmgeo geocode -g nominatim -g google > entities_geocoded.ftm.ijson

## Documentation

https://docs.investigraph.dev/lib/ftm-geocode

## Installation

Required external is [libpostal](https://github.com/openvenues/pypostal), see installation instructions there.

Once `libpostal` is installed on your system, you can install:

    pip install ftm-geocode[postal]


## Testing

    make install
    make test


## License and Copyright

`ftm_geocode`, (C) 2023 Simon Wörpel
`ftm_geocode`, (C) 2024-2025 investigativedata.io
`ftm_geocode`, (C) 2025 Data and Research Center – DARC

`ftm_geocode` is licensed under the AGPLv3 or later license.

Prior to version 0.1.0, `ftm_geocode` was released under the MIT license.

see [NOTICE](./NOTICE) and [LICENSE](./LICENSE)
