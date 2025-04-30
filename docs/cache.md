# Cache

During geocoding, addresses are first looked up in the local cache, and new geocoding results are added.

The cache is using [`anstore`](https://docs.investigraph.dev/lib/anystore) as a backend and defaults to `.anystore` subdirectory of current workdir.

To configure the store uri, use `FTMGEO_CACHE__URI` env var, for example:

    FTMGEO_CACHE__URI=redis://localhost


## Usage

    ftmgeo cache --help

Ignore cache during geocoding (new results are still written to it):

    ftmgeo geocode --no-cache ...

### Export cache

    ftmgeo cache iterate > geocoded_addresses.ftm.ijsonl
    ftmgeo cache iterate --output-format=csv > geocoded_addresses.csv

### Populate cache

Populate cache from csv or json input with these fields:\n
- cache_key: str | None
- address_id: str
- original_line: str
- result_line: str
- country: str
- lat: float
- lon: float
- geocoder: str
- geocoder_place_id: str | None = None
- geocoder_raw: str | None = None
- nuts0_id: str | None = None
- nuts1_id: str | None = None
- nuts2_id: str | None = None
- nuts3_id: str | None = None
- ts: datetime | None = None

    cat geocoded_addresses.csv | ftmgeo cache populate
