"""String-delta representation for compact scalar string evolutions.

Separates common prefix, common suffix, and changed middle segment.
"""

from srx.core.varint import decode_bytes, decode_uvarint, encode_bytes, encode_uvarint


def str_delta_parts(old: str, new: str) -> tuple[int, int, str]:
    """Find prefix length, suffix length, and middle insertion string."""
    p = 0
    lim = min(len(old), len(new))
    while p < lim and old[p] == new[p]:
        p += 1
    
    s = 0
    lim2 = min(len(old) - p, len(new) - p)
    while s < lim2 and old[len(old) - 1 - s] == new[len(new) - 1 - s]:
        s += 1
    
    mid_end = len(new) - s if s else len(new)
    mid = new[p:mid_end]
    return p, s, mid


def encode_sdelta_payload(old: str, new: str) -> bytes:
    """Encode string delta as uvarint(prefix_len) + uvarint(suffix_len) + enc_bytes(mid)."""
    p, s, mid = str_delta_parts(old, new)
    return encode_uvarint(p) + encode_uvarint(s) + encode_bytes(mid.encode("utf-8"))


def apply_sdelta(old: str, payload: bytes, offset: int) -> tuple[str, int]:
    """Apply string delta payload against reference string.
    
    Returns (reconstructed_string, new_offset).
    """
    p, offset = decode_uvarint(payload, offset)
    s, offset = decode_uvarint(payload, offset)
    mid_bytes, offset = decode_bytes(payload, offset)
    
    if p + s > len(old):
        raise ValueError(f"Invalid string delta: p({p}) + s({s}) exceeds old length({len(old)})")
    
    tail = old[len(old) - s :] if s else ""
    reconstructed = old[:p] + mid_bytes.decode("utf-8") + tail
    return reconstructed, offset
