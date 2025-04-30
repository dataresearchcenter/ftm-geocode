from unittest import TestCase

from followthemoney.proxy import EntityProxy

from ftm_geocode import model
from ftm_geocode.settings import Settings


class ModelTestCase(TestCase):
    def test_model(self):
        settings = Settings()
        if settings.libpostal:
            address = """
                OpenStreetMap Foundation
                St John’s Innovation Centre
                Cowley Road
                Cambridge
                CB4 0WS
                United Kingdom
            """
            address = model.Address.from_string(address)
            self.assertDictEqual(
                address.to_dict(),
                {
                    "remarks": ["Openstreetmap Foundation St John'S Innovation Centre"],
                    "street": ["Cowley Road"],
                    "city": ["Cambridge"],
                    "postalCode": ["Cb4 0Ws"],
                    "country": ["gb"],
                },
            )

            proxy = address.to_proxy()
            self.assertIsInstance(proxy, EntityProxy)
            self.assertDictEqual(
                proxy.to_dict(),
                {
                    "id": "addr-gb-7305a0eaef6fdebc0f6bac6066fd1e26fd7fd54a",
                    "caption": "Cambridge",
                    "schema": "Address",
                    "properties": {
                        "remarks": [
                            "Openstreetmap Foundation St John'S Innovation Centre"
                        ],
                        "street": ["Cowley Road"],
                        "city": ["Cambridge"],
                        "postalCode": ["Cb4 0Ws"],
                        "country": ["gb"],
                    },
                    "referents": [],
                    "datasets": ["default"],
                },
            )

            # less info, not so good result
            address = "DUDA-EPURENI, 737230, RO"
            address = model.Address.from_string(address, country="ro")
            address = address.to_dict()
            address["remarks"] = list(sorted(address["remarks"]))
            self.assertDictEqual(
                address,
                {
                    "remarks": ["737230", "Duda-Epureni"],
                    "street": ["Ro"],
                    "country": ["ro"],
                },
            )

            # we store postal result to access it later
            address = """
                OpenStreetMap Foundation
                St John’s Innovation Centre
                Cowley Road
                Cambridge
                CB4 0WS
                United Kingdom
            """
            address = model.Address.from_string(address)
            self.assertIsInstance(address._postal, model.PostalAddress)
            self.assertEqual(
                address._postal.to_dict(),
                {
                    "country_code": "gb",
                    "house": "Openstreetmap Foundation St John'S Innovation Centre",
                    "road": "Cowley Road",
                    "postcode": "Cb4 0Ws",
                    "city": "Cambridge",
                },
            )
