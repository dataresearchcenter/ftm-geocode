from unittest import TestCase

from followthemoney.proxy import EntityProxy

from ftm_geocode.ftm import make_address_proxy
from ftm_geocode.parsing import ParsedAddress, get_components, parse_address
from ftm_geocode.settings import Settings


class ParsingTestCase(TestCase):
    def test_parse_address(self):
        settings = Settings()
        if settings.libpostal:
            address = """
                OpenStreetMap Foundation
                St John's Innovation Centre
                Cowley Road
                Cambridge
                CB4 0WS
                United Kingdom
            """
            parsed = parse_address(address)
            self.assertIsInstance(parsed, ParsedAddress)
            self.assertIn("Cowley Road", parsed.road)
            self.assertIn("Cambridge", parsed.city)
            self.assertEqual(parsed.country_code, "gb")

            # Get components as dict
            components = get_components(address)
            self.assertIn("road", components)
            self.assertIn("city", components)
            self.assertEqual(components["country_code"], "gb")


class FtmTestCase(TestCase):
    def test_make_address_proxy(self):
        settings = Settings()
        if settings.libpostal:
            address = """
                OpenStreetMap Foundation
                St John's Innovation Centre
                Cowley Road
                Cambridge
                CB4 0WS
                United Kingdom
            """
            proxy = make_address_proxy(address)
            self.assertIsInstance(proxy, EntityProxy)
            self.assertEqual(proxy.schema.name, "Address")
            self.assertTrue(proxy.id.startswith("addr-"))
            self.assertIn("Cowley Road", proxy.first("street"))
            self.assertEqual(proxy.first("city"), "Cambridge")

            # With coordinates
            proxy = make_address_proxy(
                address,
                lat=52.2297,
                lon=0.1526,
            )
            self.assertEqual(proxy.first("latitude"), "52.2297")
            self.assertEqual(proxy.first("longitude"), "0.1526")

            # With place IDs
            proxy = make_address_proxy(address, osm_id="12345")
            self.assertEqual(proxy.id, "addr-osm-12345")
            self.assertEqual(proxy.first("osmId"), "12345")

            proxy = make_address_proxy(address, google_place_id="ChIJ...")
            self.assertEqual(proxy.id, "addr-google-ChIJ...")
            self.assertEqual(proxy.first("googlePlaceId"), "ChIJ...")
