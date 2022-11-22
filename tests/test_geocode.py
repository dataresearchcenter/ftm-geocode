from unittest import TestCase

from followthemoney import model

from ftm_geocode import geocode


class GeocodingTestCase(TestCase):
    ADDR = """Cowley Road
           Cambridge
           CB4 0WS
           United Kingdom"""

    geocoder = geocode.Geocoders.nominatim

    def test_geocode_line(self):
        result = geocode.geocode_line(
            [self.geocoder], self.ADDR, use_cache=False, country="gb"
        )
        self.assertIsInstance(result, geocode.GeocodingResult)
        self.assertEqual(
            result.address_id, "addr-gb-5490d62df3e2c7c7fd3a311d9c5c452f6b49f34d"
        )
        self.assertEqual(
            result.canonical_id, "addr-gb-171345b555e145c006613b2e69518dbc58f569e5"
        )
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
            "addr-gb-171345b555e145c006613b2e69518dbc58f569e5",
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
