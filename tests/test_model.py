from unittest import TestCase

from followthemoney.proxy import EntityProxy

from ftm_geocode import model


class ModelTestCase(TestCase):
    def test_model(self):
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
                "remarks": ["openstreetmap foundation st john's innovation centre"],
                "street": ["cowley road"],
                "city": ["cambridge"],
                "postalCode": ["cb4 0ws"],
                "country": ["GB"],
            },
        )

        proxy = address.to_proxy()
        self.assertIsInstance(proxy, EntityProxy)
        self.assertDictEqual(
            proxy.to_dict(),
            {
                "id": "addr-gb-7305a0eaef6fdebc0f6bac6066fd1e26fd7fd54a",
                "schema": "Address",
                "properties": {
                    "remarks": ["openstreetmap foundation st john's innovation centre"],
                    "street": ["cowley road"],
                    "city": ["cambridge"],
                    "postalCode": ["cb4 0ws"],
                    "country": ["GB"],
                },
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
                "remarks": ["737230", "duda-epureni"],
                "street": ["ro"],
                "country": ["RO"],
            },
        )
