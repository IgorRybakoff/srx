"""Varint, byte chunk encoding/decoding, and cryptographic hashing primitives."""

import hashlib


def sha256(data: bytes) -> bytes:
    """Compute 32-byte raw SHA-256 digest of data."""
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes) -> str:
    """Compute 64-character hex-encoded SHA-256 digest of data."""
    return hashlib.sha256(data).hexdigest()


def encode_uvarint(n: int) -> bytes:
    """Encode non-negative integer as unsigned variable-length LEB128 bytes."""
    if n < 0:
        raise ValueError(f"uvarint must be non-negative, got {n}")
    out = bytearray()
    while True:
        q = n & 0x7F
        n >>= 7
        out.append(q | (0x80 if n else 0))
        if not n:
            return bytes(out)


def decode_uvarint(buf: bytes, offset: int) -> tuple[int, int]:
    """Decode unsigned variable-length LEB128 integer from buffer at offset.
    
    Returns (value, new_offset).
    """
    n = 0
    shift = 0
    while True:
        if offset >= len(buf):
            raise IndexError("Unexpected end of buffer while decoding uvarint")
        q = buf[offset]
        offset += 1
        n |= (q & 0x7F) << shift
        if not (q & 0x80):
            return n, offset
        shift += 7


def encode_bytes(data: bytes) -> bytes:
    """Prefix bytes with length encoded as uvarint."""
    return encode_uvarint(len(data)) + data


def decode_bytes(buf: bytes, offset: int) -> tuple[bytes, int]:
    """Decode length-prefixed bytes from buffer at offset.
    
    Returns (data_bytes, new_offset).
    """
    length, offset = decode_uvarint(buf, offset)
    if offset + length > len(buf):
        raise IndexError(f"Buffer underflow: needed {length} bytes, have {len(buf) - offset}")
    return buf[offset : offset + length], offset + length


# Shorthand aliases preserving frozen v0.9 compatibility
uv = encode_uvarint
duv = decode_uvarint
enc_bytes = encode_bytes
dec_bytes = decode_bytes
