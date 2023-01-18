from unittest import TestCase

from followthemoney import model

from ftm_geocode import geocode


class GeocodingTestCase(TestCase):
    ADDR = """Cowley Road
           Cambridge
           CB4 0WS
           United Kingdom"""

    geocoder = geocode.GEOCODERS.nominatim

    def test_geocode_line(self):
        result = geocode.geocode_line(
            [self.geocoder], self.ADDR, use_cache=False, country="gb"
        )
        self.assertIsInstance(result, geocode.GeocodingResult)
        self.assertEqual(
            result.address_id,
            "addr-gb-db3268056d7dd490c8a94d16a4634329724e6980",
        )
        self.assertEqual(result.canonical_id, "addr-osm-102184726")
        self.assertEqual(
            result.original_line, "Cowley Road Cambridge CB4 0WS United Kingdom"
        )
        self.assertEqual(
            result.result_line,
            "Cowley Road, Chesterton, Cambridge, Cambridgeshire, Cambridgeshire and Peterborough, England, CB4 0AP, United Kingdom",
        )
        self.assertEqual(result.geocoder, "nominatim")

    def test_geocode_entity(self):
        proxy = model.get_proxy(
            {"schema": "Organization", "properties": {"address": [self.ADDR]}}
        )
        addressProxy, updatedProxy = geocode.geocode_proxy(
            [self.geocoder], proxy, use_cache=False
        )
        self.assertEqual(
            updatedProxy.first("addressEntity"),
            ("addr-osm-102184726"),
        )
        self.assertIn(
            "Cowley Road, Chesterton, Cambridge, Cambridgeshire, Cambridgeshire and Peterborough, England, CB4 0AP, United Kingdom",
            addressProxy.get("full"),
        )
        self.assertEqual(addressProxy.first("country"), "GB")
        self.assertEqual(addressProxy.first("city"), "cambridge")

    def test_geocode_address_entity(self):
        proxy = model.get_proxy(
            {
                "schema": "Address",
                "properties": {"full": [self.ADDR], "country": ["GB"]},
            }
        )
        addressProxy = next(
            geocode.geocode_proxy([self.geocoder], proxy, use_cache=False)
        )
        self.assertIn(
            "Cowley Road, Chesterton, Cambridge, Cambridgeshire, Cambridgeshire and Peterborough, England, CB4 0AP, United Kingdom",
            addressProxy.get("full"),
        )
        self.assertEqual(addressProxy.first("country"), "GB")
        self.assertEqual(addressProxy.first("city"), "cambridge")

        # csv output
        result = next(
            geocode.geocode_proxy(
                [self.geocoder],
                proxy,
                use_cache=False,
                output_format=geocode.Formats.csv,
            )
        )
        self.assertIsInstance(result, geocode.GeocodingResult)
