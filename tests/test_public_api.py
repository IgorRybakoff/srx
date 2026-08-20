import unittest

from srx.core.constants import REC_SNAPSHOT
from srx.core.compression import zstd
from srx.core.record import create_record
from srx.core.varint import sha256_hex
from srx.public_api import SRXCoreAPI


class TestPublicAPI(unittest.TestCase):
    def test_reconstruct_verify_contract(self):
        target = b'{"status":"ok"}\n'
        record = create_record(None, target, REC_SNAPSHOT, zstd(target))
        out = SRXCoreAPI.reconstruct(None, record)
        self.assertEqual(out, target)
        self.assertTrue(SRXCoreAPI.verify(out, sha256_hex(target)))
        self.assertFalse(SRXCoreAPI.verify(out, "00" * 32))


if __name__ == '__main__':
    unittest.main()
