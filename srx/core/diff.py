"""Structural diff algorithms and logical variant generation."""

import itertools
from typing import Any
from srx.core.sequence_ops import array_alternatives


def diff_json(a: Any, b: Any, path: tuple[str, ...] = ()) -> list[tuple]:
    """Compute standard deterministic structural diff between objects a and b."""
    ops: list[tuple] = []
    if type(a) is not type(b):
        return [("SET", path, b)]
    if isinstance(a, dict):
        ak = list(a.keys())
        bk = list(b.keys())
        # Removals first in reverse order
        for k in reversed(ak):
            if k not in b:
                ops.append(("REMOVE", path + (k,), None))
        # Recurse common keys
        for k in bk:
            if k in a:
                ops.extend(diff_json(a[k], b[k], path + (k,)))
        # Adds with target index so insertion order is deterministic
        for idx, k in enumerate(bk):
            if k not in a:
                ops.append(("ADD", path + (k,), (idx, b[k])))
        return ops
    if isinstance(a, list):
        if a != b:
            ops.append(("SET", path, b))
        return ops
    if a != b:
        ops.append(("SET", path, b))
    return ops


def diff_json_variants(a: Any, b: Any, path: tuple[str, ...] = ()) -> list[tuple[str, list[tuple]]]:
    """Generate all exact (label, ops) candidate diff variants across structured hierarchy.
    
    Dict/scalar changes are deterministic. List changes branch into candidate forms.
    """
    if type(a) is not type(b):
        return [("BASE", [("SET", path, b)])]
    if isinstance(a, dict):
        fixed: list[tuple] = []
        branches: list[list[tuple[str, list[tuple]]]] = []
        ak = list(a.keys())
        bk = list(b.keys())
        for k in reversed(ak):
            if k not in b:
                fixed.append(("REMOVE", path + (k,), None))
        for k in bk:
            if k in a:
                vv = diff_json_variants(a[k], b[k], path + (k,))
                if len(vv) == 1:
                    fixed.extend(vv[0][1])
                else:
                    branches.append(vv)
        for idx, k in enumerate(bk):
            if k not in a:
                fixed.append(("ADD", path + (k,), (idx, b[k])))
        if not branches:
            return [("BASE", fixed)]
        out: list[tuple[str, list[tuple]]] = []
        for combo in itertools.product(*branches):
            label = "+".join(x[0] for x in combo)
            ops = list(fixed)
            for _, oo in combo:
                ops.extend(oo)
            out.append((label, ops))
        return out
    if isinstance(a, list):
        if a == b:
            return [("BASE", [])]
        return array_alternatives(a, b, path)
    if a != b:
        return [("BASE", [("SET", path, b)])]
    return [("BASE", [])]
