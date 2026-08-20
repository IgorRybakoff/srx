"""Generic sequence edit candidate generators.

Produces exact sequence edit candidates (MOVE-aware, INSERT/DELETE, REORDER permutations)
using generic JSON equality and SequenceMatcher without domain-specific heuristics.
"""

import copy
import difflib
import json
from typing import Any


def _compact_json(v: Any) -> bytes:
    return json.dumps(v, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def seq_edit_ops(a: list, b: list, path: tuple) -> list[tuple]:
    """MOVE-aware exact edit candidate. Generic JSON equality; no domain knowledge."""
    work = copy.deepcopy(a)
    ops: list[tuple] = []
    i = 0
    while i < len(b):
        if i < len(work) and work[i] == b[i]:
            i += 1
            continue
        # If desired element exists later, MOVE it into place.
        src = None
        for j in range(i + 1, len(work)):
            if work[j] == b[i]:
                src = j
                break
        if src is not None:
            val = work.pop(src)
            work.insert(i, val)
            ops.append(("L_MOVE", path, (src, i)))
            i += 1
            continue
        # Otherwise insert desired target element.
        work.insert(i, copy.deepcopy(b[i]))
        ops.append(("L_INSERT", path, (i, b[i])))
        i += 1
        
    # Delete any tail not present in target after alignment.
    for j in range(len(work) - 1, len(b) - 1, -1):
        work.pop(j)
        ops.append(("L_DELETE", path, j))
        
    assert work == b, f"seq_edit_ops mismatch: work={work} != b={b}"
    return ops


def insert_delete_ops(a: list, b: list, path: tuple) -> list[tuple]:
    """Exact INSERT/DELETE candidate based on SequenceMatcher blocks.
    
    Applies opcodes forward while tracking index shift; generic JSON equality.
    """
    ak = [_compact_json(x).decode("utf-8") for x in a]
    bk = [_compact_json(x).decode("utf-8") for x in b]
    sm = difflib.SequenceMatcher(a=ak, b=bk, autojunk=False)
    ops: list[tuple] = []
    shift = 0
    
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        cur = i1 + shift
        if tag in ("delete", "replace"):
            for _ in range(i2 - i1):
                ops.append(("L_DELETE", path, cur))
            shift -= (i2 - i1)
        if tag in ("insert", "replace"):
            cur = i1 + shift
            for k, val in enumerate(b[j1:j2]):
                ops.append(("L_INSERT", path, (cur + k, val)))
            shift += (j2 - j1)
            
    # Direct simulation verification
    work = copy.deepcopy(a)
    for kind, _, data in ops:
        if kind == "L_DELETE":
            del work[data]
        else:
            idx, val = data
            work.insert(idx, copy.deepcopy(val))
    assert work == b, f"insert_delete_ops mismatch: work={work} != b={b}"
    return ops


def reorder_perm(a: list, b: list) -> list[int] | None:
    """Return target->source permutation if b is exactly a permutation of a.
    
    Handles duplicates deterministically by consuming first unused equal item.
    """
    if len(a) != len(b):
        return None
    used = [False] * len(a)
    perm: list[int] = []
    for x in b:
        found = None
        for i, y in enumerate(a):
            if not used[i] and y == x:
                found = i
                break
        if found is None:
            return None
        used[found] = True
        perm.append(found)
    return perm


def array_alternatives(a: list, b: list, path: tuple) -> list[tuple[str, list[tuple]]]:
    """Generate all exact candidate representations for an array transition."""
    alts: list[tuple[str, list[tuple]]] = [
        ("WHOLE_SET", [("SET", path, b)]),
        ("INSERT_DELETE", insert_delete_ops(a, b, path)),
        ("MOVE_AWARE", seq_edit_ops(a, b, path)),
    ]
    perm = reorder_perm(a, b)
    if perm is not None and perm != list(range(len(a))):
        alts.append(("REORDER", [("L_REORDER", path, perm)]))
    return alts
