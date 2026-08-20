"""Tests for String-Delta representation (sdelta)."""

import unittest
from srx.core.sdelta import apply_sdelta, encode_sdelta_payload, str_delta_parts


class TestStringDelta(unittest.TestCase):
    """Verify exact behavior of string delta encoding and application."""

    def test_sdelta_known_pairs(self) -> None:
        pairs = [
            ("abc", "axc"),
            ("version-5.0.json", "version-6.0.json"),
            ("привет-мир", "привет-свет"),
            ("", "x"),
            ("x", ""),
            ("sameprefixXYZtail", "sameprefix123tail"),
            ("identical", "identical"),
            ("completely_different", "1234567890"),
        ]
        for a, b in pairs:
            with self.subTest(a=a, b=b):
                payload = encode_sdelta_payload(a, b)
                reconstructed, offset = apply_sdelta(a, payload, 0)
                self.assertEqual(offset, len(payload))
                self.assertEqual(reconstructed, b)

    def test_sdelta_parts(self) -> None:
        p, s, mid = str_delta_parts("devinit-v1.2.json", "devinit-v2.5.json")
        self.assertEqual(p, len("devinit-v"))
        self.assertEqual(s, len(".json"))
        self.assertEqual(mid, "2.5")

    def test_sdelta_invalid_offset(self) -> None:
        with self.assertRaises(Exception):
            apply_sdelta("short", b"\x10\x10\x01a", 0)


if __name__ == "__main__":
    unittest.main()
