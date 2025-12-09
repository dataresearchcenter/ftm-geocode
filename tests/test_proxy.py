from unittest import TestCase

from ftmq.util import make_entity
from normality import squash_spaces

from ftm_geocode.ftm import apply_address, get_proxy_addresses, make_address_proxy

ADDR = """ OpenStreetMap Foundation
           St John's Innovation Centre
           Cowley Road
           Cambridge
           CB4 0WS
           United Kingdom"""
ADDR = squash_spaces(ADDR)


class ProxyTestCase(TestCase):
    entity = make_entity(
        {
            "id": "ent",
            "schema": "LegalEntity",
            "properties": {"address": [ADDR]},
        }
    )
    addressEntity = make_entity(
        {
            "id": "addr",
            "schema": "Address",
            "properties": {"full": [ADDR]},
        }
    )

    def test_proxy(self):
        for value in get_proxy_addresses(self.entity):
            self.assertEqual(value, ADDR)
        for value in get_proxy_addresses(self.addressEntity):
            self.assertEqual(value, ADDR)

    def test_proxy_apply(self):
        proxy = apply_address(self.entity.clone(), self.addressEntity)
        self.assertEqual(proxy.first("addressEntity"), "addr")
        self.assertIn(ADDR, proxy.get("address"))

        # merge: rewrite ids vs. not merge
        address = make_address_proxy(ADDR)
        proxy = apply_address(self.entity.clone(), address)
        self.assertEqual(proxy.first("addressEntity"), address.id)
        address = apply_address(self.addressEntity.clone(), address)
        proxy = apply_address(proxy.clone(), address)
        self.assertIn(address.id, proxy.get("addressEntity"))
        address = apply_address(self.addressEntity.clone(), address, rewrite_id=False)
        self.assertEqual(address.id, "addr")
        proxy = apply_address(self.entity.clone(), address, rewrite_id=False)
        for addressId in proxy.get("addressEntity"):
            self.assertEqual(addressId, "addr")
