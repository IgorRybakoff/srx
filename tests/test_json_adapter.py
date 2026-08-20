"""Tests for JSON Reference Format Adapter."""

import unittest
from srx.adapters.json_adapter import JSONAdapter
from srx.core.ops import apply_ops


class TestJSONAdapter(unittest.TestCase):
    """Verify JSON parsing, serialization, and structural diffing."""

    def test_parse_and_serialize(self) -> None:
        data = {"name": "srx", "version": "0.1.0", "active": True, "count": 100}
        serialized = JSONAdapter.serialize(data, pretty=True)
        parsed = JSONAdapter.parse(serialized)
        self.assertEqual(parsed, data)

    def test_structural_diff_and_apply(self) -> None:
        v1 = {
            "title": "SRX Spec",
            "tags": ["alpha", "draft"],
            "meta": {"author": "team", "year": 2026},
        }
        v2 = {
            "title": "SRX Spec v0.1",
            "tags": ["public", "release"],
            "meta": {"author": "SRX Contributors", "year": 2026, "license": "Apache-2.0"},
            "published": True,
        }

        diff_ops = JSONAdapter.structural_diff(v1, v2)
        applied = apply_ops(v1, diff_ops)
        self.assertEqual(applied, v2)

    def test_structural_diff_variants(self) -> None:
        v1 = {"items": ["a", "b", "c"]}
        v2 = {"items": ["b", "c", "d"]}
        variants = JSONAdapter.structural_diff_variants(v1, v2)
        self.assertTrue(len(variants) >= 1)
        for label, ops in variants:
            applied = apply_ops(v1, ops)
            self.assertEqual(applied, v2)


if __name__ == "__main__":
    unittest.main()
