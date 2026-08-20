"""Tests for Sparse Formatting Residuals (format_gaps)."""

import unittest
from srx.core.format_gaps import apply_format_gaps, encode_format_gaps, json_token_gaps


class TestFormatGaps(unittest.TestCase):
    """Verify exact behavior of format gap residual encoding and reconstruction."""

    def test_json_token_gaps_basic(self) -> None:
        raw = b'{\n  "key": "value",\n  "num": 42\n}\n'
        toks, gaps = json_token_gaps(raw)
        self.assertEqual(len(gaps), len(toks) + 1)

    def test_format_gap_exactness(self) -> None:
        pred = b'{\n  "a": [\n    1,\n    2\n  ]\n}\n'
        tgt = b'{"a": [1, 2]}\n'
        
        fp = encode_format_gaps(pred, tgt)
        self.assertIsNotNone(fp)
        assert fp is not None
        reconstructed = apply_format_gaps(pred, fp)
        self.assertEqual(reconstructed, tgt)

    def test_format_reject_token_change(self) -> None:
        pred = b'{\n  "a": [\n    1,\n    2\n  ]\n}\n'
        # Different value (3 instead of 2) must be rejected because semantic tokens changed
        tgt = b'{"a": [1, 3]}\n'
        fp = encode_format_gaps(pred, tgt)
        self.assertIsNone(fp)

    def test_complex_formatting_variation(self) -> None:
        pred = b'{\n  "name": "test",\n  "nested": {\n    "list": [\n      "item1",\n      "item2"\n    ]\n  }\n}\n'
        tgt = b'{"name":"test","nested":{"list":["item1", "item2"]}}'
        
        fp = encode_format_gaps(pred, tgt)
        self.assertIsNotNone(fp)
        assert fp is not None
        reconstructed = apply_format_gaps(pred, fp)
        self.assertEqual(reconstructed, tgt)


if __name__ == "__main__":
    unittest.main()
