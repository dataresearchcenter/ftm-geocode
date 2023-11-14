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
            "addr-gb-cae982ac59b76884890db911fe9faa0933e8a155",
        )
        self.assertTrue(result.canonical_id.startswith("addr-osm-"))
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
        self.assertTrue(
            updatedProxy.first("addressEntity").startswith("addr-osm-"),
        )
        self.assertIn(
            "Cowley Road, Chesterton, Cambridge, Cambridgeshire, Cambridgeshire and Peterborough, England, CB4 0AP, United Kingdom",
            addressProxy.get("full"),
        )
        self.assertEqual(addressProxy.first("country"), "GB")
        self.assertEqual(addressProxy.first("city"), "Cambridge")

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
        self.assertEqual(addressProxy.first("city"), "Cambridge")

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
