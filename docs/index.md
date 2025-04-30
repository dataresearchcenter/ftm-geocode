[![ftm-geocode on pypi](https://img.shields.io/pypi/v/ftm-geocode)](https://pypi.org/project/ftm-geocode/)
[![Python test and package](https://github.com/dataresearchcenter/ftm-geocode/actions/workflows/python.yml/badge.svg)](https://github.com/dataresearchcenter/ftm-geocode/actions/workflows/python.yml)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Coverage Status](https://coveralls.io/repos/github/dataresearchcenter/ftm-geocode/badge.svg?branch=main)](https://coveralls.io/github/dataresearchcenter/ftm-geocode?branch=main)
[![GPL-3.0 License](https://img.shields.io/pypi/l/ftm-geocode)](./LICENSE)

# ftm-geocode

Batch parse and geocode addresses from [FollowTheMoney entities](https://followthemoney.tech)

There are as well some parsing / normalization helpers.

## Features
- Parse and normalize addresses via [libpostal](https://github.com/openvenues/libpostal) and [rigour](https://opensanctions.github.io/rigour/addresses/)
- Geocoding via [geopy](https://geopy.readthedocs.io/en/stable/)
- Cache geocoding results using [anystore](https://docs.investigraph.dev/lib/anystore)
- Optional fallback geocoders when preferred geocoder doesn't match
- Create, update and merge [`Address`](https://followthemoney.tech/explorer/schemata/Address/) entities for ftm data

## Quickstart

    pip install ftm-geocode

Geocode an input stream of ftm entities with nominatim and google maps as
fallback (geocoders are tried in the given order):

    cat entities.ftm.ijson | ftmgeo geocode -g nominatim -g google > entities_geocoded.ftm.ijson
