"""Encoding and decoding routines for physical transformation payloads."""

import json
from typing import Any
from srx.core.constants import (
    E_CTX,
    E_RAW,
    E_ZSTD,
    OP_ADD,
    OP_LDELETE,
    OP_LINSERT,
    OP_LMOVE,
    OP_LREORDER,
    OP_REMOVE,
    OP_SDELTA,
    OP_SET,
)
from srx.core.compression import unzstd, zstd
from srx.core.ops import get_at
from srx.core.paths import (
    build_paths,
    decode_path_ctx,
    decode_path_raw,
    encode_path_ctx,
    encode_path_raw,
)
from srx.core.sdelta import apply_sdelta, encode_sdelta_payload
from srx.core.varint import decode_bytes, decode_uvarint, encode_bytes, encode_uvarint


def _compact_json(v: Any) -> bytes:
    return json.dumps(v, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _raw_set_piece(path: tuple[str, ...], data: Any, refobj: Any) -> tuple[bytes, str]:
    full = bytes([OP_SET]) + encode_path_raw(path) + encode_bytes(_compact_json(data))
    if isinstance(data, str):
        try:
            old = get_at(refobj, path)
        except Exception:
            old = None
        if isinstance(old, str):
            delta = bytes([OP_SDELTA]) + encode_path_raw(path) + encode_sdelta_payload(old, data)
            if len(delta) < len(full):
                return delta, "STRING_DELTA"
    return full, "SET_VALUE"


def _ctx_set_piece(
    path: tuple[str, ...], data: Any, refobj: Any, pmap: dict[tuple[str, ...], int]
) -> tuple[bytes, str]:
    full = bytes([OP_SET]) + encode_path_ctx(path, pmap) + encode_bytes(_compact_json(data))
    if isinstance(data, str):
        try:
            old = get_at(refobj, path)
        except Exception:
            old = None
        if isinstance(old, str):
            delta = bytes([OP_SDELTA]) + encode_path_ctx(path, pmap) + encode_sdelta_payload(old, data)
            if len(delta) < len(full):
                return delta, "STRING_DELTA"
    return full, "SET_VALUE"


def encode_ops_raw(ops: list[tuple], refobj: Any) -> tuple[bytes, list[str]]:
    """Encode operations using absolute path descriptors."""
    pieces: list[bytes] = []
    modes: list[str] = []
    for op in ops:
        kind = op[0]
        path = op[1]
        data = op[2] if len(op) > 2 else None
        
        if kind == "SET":
            piece, mode = _raw_set_piece(path, data, refobj)
            pieces.append(piece)
            modes.append(mode)
            continue
            
        o = bytearray()
        if kind == "ADD":
            idx, val = data
            o.append(OP_ADD)
            o += encode_path_raw(path)
            o += encode_uvarint(idx)
            o += encode_bytes(_compact_json(val))
        elif kind == "REMOVE":
            o.append(OP_REMOVE)
            o += encode_path_raw(path)
        elif kind == "L_INSERT":
            idx, val = data
            o.append(OP_LINSERT)
            o += encode_path_raw(path)
            o += encode_uvarint(idx)
            o += encode_bytes(_compact_json(val))
        elif kind == "L_DELETE":
            o.append(OP_LDELETE)
            o += encode_path_raw(path)
            o += encode_uvarint(data)
        elif kind == "L_MOVE":
            src, dst = data
            o.append(OP_LMOVE)
            o += encode_path_raw(path)
            o += encode_uvarint(src) + encode_uvarint(dst)
        elif kind == "L_REORDER":
            o.append(OP_LREORDER)
            o += encode_path_raw(path)
            o += encode_uvarint(len(data))
            for idx in data:
                o += encode_uvarint(idx)
        else:
            raise ValueError(f"Unknown operation kind {kind}")
            
        pieces.append(bytes(o))
        modes.append(kind)
        
    return encode_uvarint(len(ops)) + b"".join(pieces), modes


def encode_ops_ctx(ops: list[tuple], refobj: Any) -> tuple[bytes, list[str]]:
    """Encode operations using context path dictionary indexes."""
    paths = build_paths(refobj)
    pmap = {p: i for i, p in enumerate(paths)}
    pieces: list[bytes] = []
    modes: list[str] = []
    
    code_map = {
        "ADD": OP_ADD,
        "REMOVE": OP_REMOVE,
        "L_INSERT": OP_LINSERT,
        "L_DELETE": OP_LDELETE,
        "L_MOVE": OP_LMOVE,
        "L_REORDER": OP_LREORDER,
    }
    
    for op in ops:
        kind = op[0]
        path = op[1]
        data = op[2] if len(op) > 2 else None
        
        if kind == "SET":
            piece, mode = _ctx_set_piece(path, data, refobj, pmap)
            pieces.append(piece)
            modes.append(mode)
            continue
            
        code = code_map[kind]
        o = bytearray()
        o.append(code)
        o += encode_path_ctx(path, pmap)
        
        if kind == "ADD":
            idx, val = data
            o += encode_uvarint(idx) + encode_bytes(_compact_json(val))
        elif kind == "L_INSERT":
            idx, val = data
            o += encode_uvarint(idx) + encode_bytes(_compact_json(val))
        elif kind == "L_DELETE":
            o += encode_uvarint(data)
        elif kind == "L_MOVE":
            src, dst = data
            o += encode_uvarint(src) + encode_uvarint(dst)
        elif kind == "L_REORDER":
            o += encode_uvarint(len(data))
            for idx in data:
                o += encode_uvarint(idx)
                
        pieces.append(bytes(o))
        modes.append(kind)
        
    return encode_uvarint(len(ops)) + b"".join(pieces), modes


def decode_ops_ctx(raw: bytes, refobj: Any) -> list[tuple]:
    """Decode context-path encoded operations against reference object structure."""
    paths = build_paths(refobj)
    i = 0
    n, i = decode_uvarint(raw, i)
    ops: list[tuple] = []
    
    for _ in range(n):
        code = raw[i]
        i += 1
        path, i = decode_path_ctx(raw, i, paths)
        
        if code == OP_SET:
            v, i = decode_bytes(raw, i)
            ops.append(("SET", path, json.loads(v)))
        elif code == OP_SDELTA:
            oldv = get_at(refobj, path)
            if not isinstance(oldv, str):
                raise ValueError("sdelta reference is not a string")
            nv, i = apply_sdelta(oldv, raw, i)
            ops.append(("SET", path, nv))
        elif code == OP_ADD:
            idx, i = decode_uvarint(raw, i)
            v, i = decode_bytes(raw, i)
            ops.append(("ADD", path, (idx, json.loads(v))))
        elif code == OP_REMOVE:
            ops.append(("REMOVE", path, None))
        elif code == OP_LINSERT:
            idx, i = decode_uvarint(raw, i)
            v, i = decode_bytes(raw, i)
            ops.append(("L_INSERT", path, (idx, json.loads(v))))
        elif code == OP_LDELETE:
            idx, i = decode_uvarint(raw, i)
            ops.append(("L_DELETE", path, idx))
        elif code == OP_LMOVE:
            src, i = decode_uvarint(raw, i)
            dst, i = decode_uvarint(raw, i)
            ops.append(("L_MOVE", path, (src, dst)))
        elif code == OP_LREORDER:
            nn, i = decode_uvarint(raw, i)
            perm: list[int] = []
            for _ in range(nn):
                q, i = decode_uvarint(raw, i)
                perm.append(q)
            ops.append(("L_REORDER", path, perm))
        else:
            raise ValueError(f"Unknown operation code {code}")
            
    if i != len(raw):
        raise ValueError(f"Trailing bytes in decode_ops_ctx ({len(raw) - i} bytes left)")
    return ops


def encode_transform_candidates(ops: list[tuple], refobj: Any) -> list[tuple[str, bytes, int, list[str]]]:
    """Encode operations into physical encoding candidates: RAW_OPS, ZSTD_OPS, CTX_PATHS."""
    raw, modes_raw = encode_ops_raw(ops, refobj)
    z = zstd(raw)
    ctx, modes_ctx = encode_ops_ctx(ops, refobj)
    return [
        ("RAW_OPS", bytes([E_RAW]) + raw, len(raw), modes_raw),
        ("ZSTD_OPS", bytes([E_ZSTD]) + z, len(raw), modes_raw),
        ("CTX_PATHS", bytes([E_CTX]) + ctx, len(raw), modes_ctx),
    ]


def decode_transform(blob: bytes, refobj: Any) -> list[tuple]:
    """Decode transform blob (with 1-byte encoding header) into logical operations."""
    typ = blob[0]
    payload = blob[1:]
    
    if typ == E_RAW:
        i = 0
        n, i = decode_uvarint(payload, i)
        ops: list[tuple] = []
        for _ in range(n):
            code = payload[i]
            i += 1
            path, i = decode_path_raw(payload, i)
            if code == OP_SET:
                v, i = decode_bytes(payload, i)
                ops.append(("SET", path, json.loads(v)))
            elif code == OP_SDELTA:
                oldv = get_at(refobj, path)
                if not isinstance(oldv, str):
                    raise ValueError("sdelta reference is not a string")
                nv, i = apply_sdelta(oldv, payload, i)
                ops.append(("SET", path, nv))
            elif code == OP_ADD:
                idx, i = decode_uvarint(payload, i)
                v, i = decode_bytes(payload, i)
                ops.append(("ADD", path, (idx, json.loads(v))))
            elif code == OP_REMOVE:
                ops.append(("REMOVE", path, None))
            elif code == OP_LINSERT:
                idx, i = decode_uvarint(payload, i)
                v, i = decode_bytes(payload, i)
                ops.append(("L_INSERT", path, (idx, json.loads(v))))
            elif code == OP_LDELETE:
                idx, i = decode_uvarint(payload, i)
                ops.append(("L_DELETE", path, idx))
            elif code == OP_LMOVE:
                src, i = decode_uvarint(payload, i)
                dst, i = decode_uvarint(payload, i)
                ops.append(("L_MOVE", path, (src, dst)))
            elif code == OP_LREORDER:
                nn, i = decode_uvarint(payload, i)
                perm: list[int] = []
                for _ in range(nn):
                    q, i = decode_uvarint(payload, i)
                    perm.append(q)
                ops.append(("L_REORDER", path, perm))
            else:
                raise ValueError(f"Unknown operation code {code}")
        if i != len(payload):
            raise ValueError(f"Trailing bytes in decode_transform RAW ({len(payload) - i} left)")
        return ops
        
    if typ == E_ZSTD:
        return decode_transform(bytes([E_RAW]) + unzstd(payload), refobj)
        
    if typ == E_CTX:
        return decode_ops_ctx(payload, refobj)
        
    raise ValueError(f"Unknown transform encoding type {typ}")
