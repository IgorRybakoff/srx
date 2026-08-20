"""Tests for physical transformation encoding and decoding."""

import unittest
from srx.core.codec import decode_transform, encode_transform_candidates
from srx.core.diff import diff_json
from srx.core.ops import apply_ops


class TestTransformCodecs(unittest.TestCase):
    """Verify transform encoding candidates (RAW, ZSTD/COMPRESSED, CTX)."""

    def test_transform_roundtrip_all_encodings(self) -> None:
        v1 = {
            "name": "project",
            "version": "1.0.0",
            "dependencies": {
                "lib-a": "^1.0",
                "lib-b": "^2.0",
                "lib-c": "^3.0",
            },
            "scripts": ["build", "test", "lint"],
        }
        v2 = {
            "name": "project",
            "version": "1.1.0",
            "dependencies": {
                "lib-a": "^1.1",
                "lib-c": "^3.0",
                "lib-d": "^1.0",
            },
            "scripts": ["build", "test", "lint", "deploy"],
        }

        ops = diff_json(v1, v2)
        candidates = encode_transform_candidates(ops, v1)
        self.assertEqual(len(candidates), 3)

        for enc_name, blob, raw_len, modes in candidates:
            with self.subTest(enc_name=enc_name):
                decoded_ops = decode_transform(blob, v1)
                result = apply_ops(v1, decoded_ops)
                self.assertEqual(result, v2)


if __name__ == "__main__":
    unittest.main()
