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
            result.address_id,
            "addr-gb-db3268056d7dd490c8a94d16a4634329724e6980",
        )
        # FIXME
        self.assertIn(
            result.canonical_id,
            (
                "addr-gb-7305a0eaef6fdebc0f6bac6066fd1e26fd7fd54a",
                "addr-gb-79c261d440e67bbc17527dbeee5bf437e170e127",
            ),
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
        # FIXME
        self.assertIn(
            updatedProxy.first("addressEntity"),
            (
                "addr-gb-7305a0eaef6fdebc0f6bac6066fd1e26fd7fd54a",
                "addr-gb-79c261d440e67bbc17527dbeee5bf437e170e127",
            ),
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
