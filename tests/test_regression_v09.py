"""Regression tests preserving frozen SRX v0.9 algorithmic baseline behavior."""

import unittest
from srx.adapters.json_adapter import JSONAdapter
from srx.core.compression import unzstd, zstd
from srx.core.constants import REC_STRUCT
from srx.core.evaluate import evaluate_structural
from srx.core.format_gaps import apply_format_gaps, encode_format_gaps
from srx.core.record import create_record, encode_structural_payload
from srx.core.sdelta import apply_sdelta, encode_sdelta_payload
from srx.core.varint import sha256_hex
from srx.reconstruct.reconstructor import SRXReconstructor


class TestRegressionV09(unittest.TestCase):
    """Ensure zero deviation from frozen v0.9 test assertions."""

    def test_v09_sdelta_edge_cases(self) -> None:
        pairs = [
            ("abc", "axc"),
            ("version-5.0.json", "version-6.0.json"),
            ("привет-мир", "привет-свет"),
            ("", "x"),
            ("sameprefixXYZtail", "sameprefix123tail"),
        ]
        for idx, (a, b) in enumerate(pairs):
            with self.subTest(idx=idx, a=a, b=b):
                p = encode_sdelta_payload(a, b)
                out, offset = apply_sdelta(a, p, 0)
                self.assertEqual(offset, len(p))
                self.assertEqual(out, b)

    def test_v09_format_gap_exactness(self) -> None:
        pred = b'{\n  "a": [\n    1,\n    2\n  ]\n}\n'
        tgt = b'{"a": [1, 2]}\n'
        fp = encode_format_gaps(pred, tgt)
        self.assertIsNotNone(fp)
        assert fp is not None
        self.assertEqual(apply_format_gaps(pred, fp), tgt)

    def test_v09_format_reject_token_change(self) -> None:
        pred = b'{\n  "a": [\n    1,\n    2\n  ]\n}\n'
        tgt = b'{"a": [1, 3]}\n'
        self.assertIsNone(encode_format_gaps(pred, tgt))

    def test_devinit_schema_roundtrips(self) -> None:
        v1 = {"$schema": "http://json-schema.org/draft-07/schema#", "version": "1.0", "type": "object"}
        v2 = {"$schema": "http://json-schema.org/draft-07/schema#", "version": "2.0", "type": "object", "auth": True}
        
        ref = JSONAdapter.serialize(v1, pretty=True)
        tgt = JSONAdapter.serialize(v2, pretty=True)
        
        best, _ = evaluate_structural(ref, tgt)
        inner = encode_structural_payload(
            best["transform_blob"],
            best["residual_type"],
            best["residual_blob"],
        )
        rec = create_record(ref, tgt, REC_STRUCT, inner)
        reconstructed = SRXReconstructor.reconstruct(ref, rec)
        self.assertEqual(reconstructed, tgt)
        self.assertEqual(sha256_hex(reconstructed), sha256_hex(tgt))


if __name__ == "__main__":
    unittest.main()
