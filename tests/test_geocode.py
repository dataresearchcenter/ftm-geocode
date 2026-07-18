from unittest import TestCase

from ftmq.util import make_entity
from normality import squash_spaces

from ftm_geocode.geocode import GEOCODERS, geocode_line, geocode_proxy
from ftm_geocode.model import GeocodingResult
from ftm_geocode.parsing import USE_LIBPOSTAL


class GeocodingTestCase(TestCase):
    ADDR = squash_spaces(
        """Cowley Road
           Cambridge
           CB4 0WS
           United Kingdom"""
    )

    geocoder = GEOCODERS.nominatim

    def test_geocode_line(self):
        result = geocode_line([self.geocoder], self.ADDR, use_cache=False, country="gb")
        self.assertIsInstance(result, GeocodingResult)
        self.assertTrue(result.address_id.startswith("addr-osm-"))
        self.assertEqual(
            result.original_line, "Cowley Road Cambridge CB4 0WS United Kingdom"
        )
        self.assertStartsWith(
            result.result_line,
            "Cowley Road, Chesterton, Cambridge, Cambridgeshire, Cambridgeshire and Peterborough, England",
        )
        self.assertEqual(result.geocoder, "nominatim")

    def test_geocode_entity(self):
        proxy = make_entity(
            {
                "id": "test-org",
                "schema": "Organization",
                "properties": {"address": [self.ADDR], "country": ["gb"]},
            }
        )
        addressProxy, updatedProxy = geocode_proxy(
            [self.geocoder], proxy, use_cache=False
        )
        self.assertTrue(
            updatedProxy.first("addressEntity").startswith("addr-osm-"),
        )
        # Check that the address contains key components (formatting may vary)
        full = addressProxy.first("full")
        self.assertIn("Cowley Road", full)
        self.assertEqual(addressProxy.first("country"), "gb")
        if USE_LIBPOSTAL:
            self.assertEqual(addressProxy.first("city"), "Cambridge")

    def test_geocode_address_entity(self):
        proxy = make_entity(
            {
                "id": "test-addr",
                "schema": "Address",
                "properties": {"full": [self.ADDR], "country": ["gb"]},
            }
        )
        addressProxy = next(geocode_proxy([self.geocoder], proxy, use_cache=False))
        # Check that the address contains key components (formatting may vary by libpostal version)
        full = " ".join(addressProxy.get("full"))
        self.assertIn("Cowley Road", full)
        self.assertIn("Cambridge", full)
        self.assertEqual(addressProxy.first("country"), "gb")
        if USE_LIBPOSTAL:
            self.assertEqual(addressProxy.first("city"), "Cambridge")
