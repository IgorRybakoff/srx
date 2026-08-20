"""Tests for generic sequence candidate generators."""

import unittest
from srx.core.ops import apply_ops
from srx.core.sequence_ops import insert_delete_ops, reorder_perm, seq_edit_ops


class TestSequenceOps(unittest.TestCase):
    """Verify sequence edit candidates (MOVE-aware, INSERT/DELETE, REORDER)."""

    def test_seq_edit_ops_move(self) -> None:
        a = [1, 2, 3, 4, 5]
        b = [5, 1, 2, 3, 4]
        ops = seq_edit_ops(a, b, ("items",))
        root = {"items": a}
        result = apply_ops(root, ops)
        self.assertEqual(result["items"], b)

    def test_insert_delete_ops(self) -> None:
        a = ["apple", "banana", "cherry"]
        b = ["banana", "date", "cherry", "elderberry"]
        ops = insert_delete_ops(a, b, ("fruits",))
        root = {"fruits": a}
        result = apply_ops(root, ops)
        self.assertEqual(result["fruits"], b)

    def test_reorder_perm(self) -> None:
        a = ["x", "y", "z", "w"]
        b = ["w", "z", "y", "x"]
        perm = reorder_perm(a, b)
        self.assertIsNotNone(perm)
        assert perm is not None
        reordered = [a[i] for i in perm]
        self.assertEqual(reordered, b)

    def test_reorder_perm_duplicates(self) -> None:
        a = [1, 2, 2, 3]
        b = [2, 3, 1, 2]
        perm = reorder_perm(a, b)
        self.assertIsNotNone(perm)
        assert perm is not None
        reordered = [a[i] for i in perm]
        self.assertEqual(reordered, b)


if __name__ == "__main__":
    unittest.main()
