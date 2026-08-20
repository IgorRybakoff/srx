import unittest

from srx.adapters.json_adapter import JSONAdapter
from srx.core.constants import REC_STRUCT
from srx.core.evaluate import evaluate_structural
from srx.core.record import create_record, encode_structural_payload
from srx.reconstruct.reconstructor import SRXReconstructor


class TestIntegrityFailures(unittest.TestCase):
    def _record_with_residual(self):
        # Formatting difference forces an exact residual on top of structural change.
        ref = b'{\n  "a": 1,\n  "items": [1, 2]\n}\n'
        tgt = b'{"a":2,"items":[1,2]}\n'
        best, _ = evaluate_structural(ref, tgt)
        inner = encode_structural_payload(best['transform_blob'], best['residual_type'], best['residual_blob'])
        return ref, tgt, bytearray(create_record(ref, tgt, REC_STRUCT, inner))

    def test_wrong_reference_fails(self):
        ref, tgt, record = self._record_with_residual()
        wrong_ref = ref.replace(b'"a": 1', b'"a": 9')
        with self.assertRaises(ValueError):
            SRXReconstructor.reconstruct(wrong_ref, bytes(record))

    def test_missing_reference_fails(self):
        ref, tgt, record = self._record_with_residual()
        with self.assertRaises(ValueError):
            SRXReconstructor.reconstruct(None, bytes(record))

    def test_corrupted_payload_fails_before_output(self):
        ref, tgt, record = self._record_with_residual()
        # Flip a byte in the payload, not the target hash header.
        self.assertGreater(len(record), 90)
        record[-1] ^= 0x01
        with self.assertRaises(Exception):
            SRXReconstructor.reconstruct(ref, bytes(record))


if __name__ == '__main__':
    unittest.main()
