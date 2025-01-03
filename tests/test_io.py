from ftm_geocode.io import LatLonRow, PostalRow, read_latlon_csv, read_postal_csv


def test_io(fixtures_path):
    tested = False
    for row in read_postal_csv(fixtures_path / "addresses.csv"):
        assert isinstance(row, PostalRow)
        if row.country == "United Kingdom":
            assert row.extra == "This is OSM office!"
        tested = True
    assert tested

    row = next(read_latlon_csv(fixtures_path / "coords.csv"))
    assert isinstance(row, LatLonRow)
    assert row.description == "wherever"
