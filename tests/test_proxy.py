from unittest import TestCase

from ftmq.util import make_proxy
from normality import collapse_spaces

from ftm_geocode import util
from ftm_geocode.model import Address

ADDR = """ OpenStreetMap Foundation
           St John’s Innovation Centre
           Cowley Road
           Cambridge
           CB4 0WS
           United Kingdom"""
ADDR = collapse_spaces(ADDR)


class ProxyTestCase(TestCase):
    entity = make_proxy(
        {
            "id": "ent",
            "schema": "LegalEntity",
            "properties": {"address": [ADDR]},
        }
    )
    addressEntity = make_proxy(
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
        proxy = util.apply_address(self.entity.clone(), self.addressEntity)
        self.assertEqual(proxy.first("addressEntity"), "addr")
        self.assertIn(ADDR, proxy.get("address"))

        # merge: rewrite ids  vs. not merge
        address = Address.from_string(ADDR).to_proxy()
        proxy = util.apply_address(self.entity.clone(), address)
        self.assertEqual(proxy.first("addressEntity"), address.id)
        address = util.apply_address(self.addressEntity.clone(), address)
        proxy = util.apply_address(proxy.clone(), address)
        self.assertIn(address.id, proxy.get("addressEntity"))
        address = util.apply_address(
            self.addressEntity.clone(), address, rewrite_id=False
        )
        self.assertEqual(address.id, "addr")
        proxy = util.apply_address(self.entity.clone(), address, rewrite_id=False)
        for addressId in proxy.get("addressEntity"):
            self.assertEqual(addressId, "addr")
