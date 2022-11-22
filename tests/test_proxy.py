from unittest import TestCase

from followthemoney import model

from ftm_geocode import util

ADDR = """ OpenStreetMap Foundation
           St John’s Innovation Centre
           Cowley Road
           Cambridge
           CB4 0WS
           United Kingdom"""


class ProxyTestCase(TestCase):
    entity = model.get_proxy(
        {
            "id": "ent",
            "schema": "LegalEntity",
            "properties": {"address": [ADDR]},
        }
    )
    addressEntity = model.get_proxy(
        {
            "id": "addr",
            "schema": "Address",
            "properties": {"full": [ADDR]},
        }
    )

    def test_proxy(self):
        for value in util.get_proxy_addresses(self.entity):
            self.assertEqual(value, ADDR)
        for value in util.get_proxy_addresses(self.addressEntity):
            self.assertEqual(value, ADDR)

    def test_proxy_apply(self):
        proxy = util.apply_address(self.entity, self.addressEntity)
        self.assertEqual(proxy.first("addressEntity"), "addr")
