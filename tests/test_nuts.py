from unittest import TestCase

from followthemoney import model

from ftm_geocode import geocode, nuts
from ftm_geocode.model import get_coords


class NutsTestCase(TestCase):
    addressEntity = model.get_proxy(
        {
            "id": "addr",
            "schema": "Address",
            "properties": {"full": ["Alexanderplatz, Berlin, Germany"]},
        }
    )
    ukAddress = model.get_proxy(
        {
            "id": "uk",
            "schema": "Address",
            "properties": {"full": ["Cowley Road, Cambridge, CB4 0WS, United Kingdom"]},
        }
    )
    outside = model.get_proxy(
        {
            "id": "outside",
            "schema": "Address",
            "properties": {
                "full": ["251 LITTLE FALLS DRIVE, WILMINGTON, New Castle, DE, 19808"],
                "country": ["us"],
            },
        }
    )

    def test_nuts_apply(self):
        res = geocode.geocode_proxy([geocode.GEOCODERS.nominatim], self.addressEntity)
        address = list(res)[0]
        coords = get_coords(address)
        codes = nuts.get_nuts_codes(*coords)
        self.assertIsInstance(codes, nuts.Nuts)
        self.assertDictEqual(
            codes.dict(),
            {
                "nuts0": "Deutschland",
                "nuts0_id": "DE",
                "nuts1": "Berlin",
                "nuts1_id": "DE3",
                "nuts2": "Berlin",
                "nuts2_id": "DE30",
                "nuts3": "Berlin",
                "nuts3_id": "DE300",
                "country": "DE",
            },
        )
        res = geocode.geocode_proxy([geocode.GEOCODERS.nominatim], self.ukAddress)
        address = list(res)[0]
        coords = get_coords(address)
        codes = nuts.get_nuts_codes(*coords)
        self.assertDictEqual(
            codes.dict(),
            {
                "nuts0": "United Kingdom",
                "nuts0_id": "UK",
                "nuts1": "East of England",
                "nuts1_id": "UKH",
                "nuts2": "East Anglia",
                "nuts2_id": "UKH1",
                "nuts3": "Cambridgeshire CC",
                "nuts3_id": "UKH12",
                "country": "UK",
            },
        )

        res = geocode.geocode_proxy([geocode.GEOCODERS.arcgis], self.outside)
        address = list(res)[0]
        coords = get_coords(address)
        codes = nuts.get_nuts_codes(*coords)
        self.assertIsNone(codes)
