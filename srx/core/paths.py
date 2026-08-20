"""Path serialization and stateful context path codec for structural representations."""

from typing import Any
from srx.core.varint import decode_bytes, decode_uvarint, encode_bytes, encode_uvarint


def build_paths(obj: Any) -> list[tuple[str, ...]]:
    """Build list of all distinct paths in a structured JSON object in preorder traversal."""
    arr: list[tuple[str, ...]] = []
    
    def rec(x: Any, p: tuple[str, ...] = ()) -> None:
        arr.append(p)
        if isinstance(x, dict):
            for k, v in x.items():
                rec(v, p + (str(k),))
        elif isinstance(x, list):
            for i, v in enumerate(x):
                rec(v, p + (str(i),))
                
    rec(obj)
    return arr


def encode_path_raw(path: tuple[str, ...]) -> bytes:
    """Encode path as uvarint(length) followed by length-prefixed path segments."""
    o = bytearray(encode_uvarint(len(path)))
    for p in path:
        o += encode_bytes(p.encode("utf-8"))
    return bytes(o)


def decode_path_raw(buf: bytes, offset: int) -> tuple[tuple[str, ...], int]:
    """Decode raw path tuple from buffer."""
    n, offset = decode_uvarint(buf, offset)
    p: list[str] = []
    for _ in range(n):
        x, offset = decode_bytes(buf, offset)
        p.append(x.decode("utf-8"))
    return tuple(p), offset


def encode_path_ctx(path: tuple[str, ...], pmap: dict[tuple[str, ...], int]) -> bytes:
    """Encode path using reference path dictionary context for maximum compression."""
    if path in pmap:
        return b"\x00" + encode_uvarint(pmap[path])
    parent = path[:-1]
    if parent not in pmap:
        raise ValueError(f"Unknown parent path {parent} for path {path}")
    return b"\x01" + encode_uvarint(pmap[parent]) + encode_bytes(path[-1].encode("utf-8"))


def decode_path_ctx(buf: bytes, offset: int, paths: list[tuple[str, ...]]) -> tuple[tuple[str, ...], int]:
    """Decode context-aware path from buffer using reference paths table."""
    kind = buf[offset]
    offset += 1
    pid, offset = decode_uvarint(buf, offset)
    if kind == 0:
        return paths[pid], offset
    key, offset = decode_bytes(buf, offset)
    return paths[pid] + (key.decode("utf-8"),), offset


# Shorthand aliases preserving v0.9 compatibility
pathenc = encode_path_raw
pathdec = decode_path_raw
enc_path_ctx = encode_path_ctx
dec_path_ctx = decode_path_ctx
