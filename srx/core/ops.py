"""Object tree manipulation and operations application."""

import copy
import json
from typing import Any


def parent_at(obj: Any, path: tuple[str, ...]) -> tuple[Any, str | None]:
    """Retrieve parent container and final key/index for a given path."""
    cur = obj
    for p in path[:-1]:
        cur = cur[int(p)] if isinstance(cur, list) else cur[p]
    return cur, path[-1] if path else None


def get_at(obj: Any, path: tuple[str, ...]) -> Any:
    """Retrieve element at path in structured object."""
    cur = obj
    for p in path:
        cur = cur[int(p)] if isinstance(cur, list) else cur[p]
    return cur


def insert_dict_at(d: dict, key: str, val: Any, idx: int) -> None:
    """Insert key-value pair into dictionary at specific index preserving insertion order."""
    items = [(k, v) for k, v in d.items() if k != key]
    idx = max(0, min(idx, len(items)))
    items.insert(idx, (key, val))
    d.clear()
    d.update(items)


def apply_ops(obj: Any, ops: list[tuple]) -> Any:
    """Apply a list of logical transformations to object, returning updated object."""
    # Deep copy preserving dictionary key insertion order
    x = json.loads(json.dumps(obj, ensure_ascii=False))
    
    for op in ops:
        kind = op[0]
        path = op[1]
        data = op[2] if len(op) > 2 else None
        
        if not path:
            if kind == "SET":
                x = data
                continue
            raise ValueError(f"Root operation must be SET, got {kind}")
            
        par, key = parent_at(x, path)
        
        if kind == "SET":
            if isinstance(par, list):
                par[int(key)] = data
            else:
                par[key] = data
        elif kind == "REMOVE":
            if isinstance(par, list):
                del par[int(key)]
            else:
                del par[key]
        elif kind == "ADD":
            idx, val = data
            if isinstance(par, list):
                par.insert(idx, val)
            else:
                insert_dict_at(par, key, val, idx)
        elif kind == "L_INSERT":
            arr = get_at(x, path)
            idx, val = data
            arr.insert(idx, copy.deepcopy(val))
        elif kind == "L_DELETE":
            arr = get_at(x, path)
            del arr[data]
        elif kind == "L_MOVE":
            arr = get_at(x, path)
            src, dst = data
            val = arr.pop(src)
            arr.insert(dst, val)
        elif kind == "L_REORDER":
            arr = get_at(x, path)
            old = list(arr)
            arr[:] = [copy.deepcopy(old[i]) for i in data]
        else:
            raise ValueError(f"Unknown operation kind: {kind}")
            
    return x
