from unittest import TestCase

from ftmq.util import make_entity

from ftm_geocode import nuts
from ftm_geocode.ftm import get_proxy_coords
from ftm_geocode.geocode import GEOCODERS, geocode_line, geocode_proxy


class NutsTestCase(TestCase):
    addressEntity = make_entity(
        {
            "id": "addr",
            "schema": "Address",
            "properties": {"full": ["Alexanderplatz, Berlin, Germany"]},
        }
    )
    ukAddress = make_entity(
        {
            "id": "uk",
            "schema": "Address",
            "properties": {"full": ["Cowley Road, Cambridge, CB4 0WS, United Kingdom"]},
        }
    )
    outside = make_entity(
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
        res = geocode_proxy([GEOCODERS.nominatim], self.addressEntity)
        address = list(res)[0]
        coords = get_proxy_coords(address)
        n3 = nuts.get_nuts(*coords)
        self.assertIsInstance(n3, nuts.Nuts3)
        self.assertDictEqual(
            n3.model_dump(),
            {
                "nuts1": "Berlin",
                "nuts1_id": "DE3",
                "nuts2": "Berlin",
                "nuts2_id": "DE30",
                "nuts3": "Berlin",
                "nuts3_id": "DE300",
                "country": "DE",
                "country_name": "Germany",
                "path": "DE/DE3/DE30/DE300",
            },
        )
        res = geocode_proxy([GEOCODERS.nominatim], self.ukAddress)
        address = list(res)[0]
        coords = get_proxy_coords(address)
        n3 = nuts.get_nuts(*coords)
        self.assertDictEqual(
            n3.model_dump(),
            {
                "nuts1": "East of England",
                "nuts1_id": "UKH",
                "nuts2": "East Anglia",
                "nuts2_id": "UKH1",
                "nuts3": "Cambridgeshire CC",
                "nuts3_id": "UKH12",
                "country": "UK",
                "country_name": "United Kingdom",
                "path": "UK/UKH/UKH1/UKH12",
            },
        )

        res = geocode_proxy([GEOCODERS.arcgis], self.outside)
        address = list(res)[0]
        coords = get_proxy_coords(address)
        n3 = nuts.get_nuts(*coords)
        self.assertIsNone(n3)

    def test_nuts_apply_to_result(self):
        res = geocode_line([GEOCODERS.nominatim], self.addressEntity.caption)
        res.apply_nuts()
        self.assertEqual(res.nuts1_id, "DE3")
        self.assertEqual(res.nuts3_id, "DE300")

    def test_nuts_apply_during_geocode(self):
        res = geocode_line(
            [GEOCODERS.nominatim],
            "Axel Springer Straße, Berlin",
            country="de",
            use_cache=False,
            apply_nuts=True,
        )
        self.assertEqual(res.nuts1_id, "DE3")
        self.assertEqual(res.nuts3_id, "DE300")

        res = geocode_line(
            [GEOCODERS.nominatim],
            "Axel Springer Straße, Berlin",
            country="de",
            use_cache=True,
            apply_nuts=True,
        )
        self.assertEqual(res.nuts1_id, "DE3")
        self.assertEqual(res.nuts3_id, "DE300")

    def test_nuts_logic(self):
        self.assertEqual(nuts.get_nuts_name("DE"), "Deutschland")
        self.assertEqual(nuts.get_nuts_name("DE3"), "Berlin")
        self.assertEqual(nuts.get_nuts_name("DE30"), "Berlin")
        self.assertEqual(nuts.get_nuts_name("DE300"), "Berlin")
        self.assertEqual(nuts.get_nuts_path("DE300"), "DE/DE3/DE30/DE300")
