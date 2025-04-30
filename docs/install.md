## Base usage

`ftm_geocode` works with python 3.11 or later.

    pip install ftm_geocode

## Libpostal

To parse address strings in its parts (street, postcode, ...) which is very useful to propagate `Address` entity data, the optional external dependency [libpostal](https://github.com/openvenues/pypostal) is used.

[libpostal install instructions](https://github.com/openvenues/pypostal?tab=readme-ov-file#installation)

Once `libpostal` is installed on your system, you can install `ftm_geocode` with the optional postal python binding:

    pip install ftm-geocode[postal]

To use `libpostal`, turn it on via the env var `FTMGEO_LIBPOSTAL=1`
