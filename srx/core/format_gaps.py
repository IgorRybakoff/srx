"""Format Gaps: Sparse formatting residual for exact JSON whitespace/layout reconstruction.

Separates syntactic tokens from whitespace gaps. If tokens match identically,
encodes only the changed whitespace gaps without storing duplicated payload.
"""

from srx.core.varint import decode_bytes, decode_uvarint, encode_bytes, encode_uvarint

_WS = set(b" \t\r\n")


def json_token_gaps(data: bytes) -> tuple[list[bytes], list[bytes]]:
    """Tokenize raw JSON bytes into syntactic tokens and intermediate whitespace gaps."""
    gaps: list[bytes] = []
    toks: list[bytes] = []
    i = 0
    n = len(data)
    
    while True:
        st = i
        while i < n and data[i] in _WS:
            i += 1
        gaps.append(data[st:i])
        if i >= n:
            break
        c = data[i]
        if c in b"{}[],:":
            toks.append(data[i : i + 1])
            i += 1
            continue
        if c == 34:  # JSON double quote string
            st = i
            i += 1
            while i < n:
                if data[i] == 92:  # Backslash escape
                    i += 2
                    continue
                if data[i] == 34:
                    i += 1
                    break
                i += 1
            toks.append(data[st:i])
            continue
        st = i
        while i < n and data[i] not in _WS and data[i] not in b"{}[],:":
            i += 1
        toks.append(data[st:i])
        
    return toks, gaps


def encode_format_gaps(pred: bytes, target: bytes) -> bytes | None:
    """Compute sparse formatting gap patch between predicted formatted JSON and target JSON.
    
    Returns encoded bytes if tokens match, or None if semantic tokens differ.
    """
    pt, pg = json_token_gaps(pred)
    tt, tg = json_token_gaps(target)
    
    if pt != tt or len(pg) != len(tg):
        return None
    
    changes = [(i, g) for i, (a, g) in enumerate(zip(pg, tg)) if a != g]
    out = bytearray(encode_uvarint(len(changes)))
    prev = 0
    for k, (idx, g) in enumerate(changes):
        d = idx if k == 0 else idx - prev
        out += encode_uvarint(d) + encode_bytes(g)
        prev = idx
        
    return bytes(out)


def apply_format_gaps(pred: bytes, patch: bytes) -> bytes:
    """Apply sparse formatting gaps patch to predicted JSON bytes to restore exact target layout."""
    toks, gaps = json_token_gaps(pred)
    i = 0
    n, i = decode_uvarint(patch, i)
    prev = 0
    
    for k in range(n):
        d, i = decode_uvarint(patch, i)
        idx = d if k == 0 else prev + d
        g, i = decode_bytes(patch, i)
        if idx >= len(gaps):
            raise ValueError(f"Format gap index {idx} out of range (max {len(gaps) - 1})")
        gaps[idx] = g
        prev = idx
        
    if i != len(patch):
        raise ValueError(f"Trailing unconsumed bytes in format patch ({len(patch) - i} bytes left)")
    
    out = bytearray()
    for j, t in enumerate(toks):
        out += gaps[j] + t
    out += gaps[-1]
    
    return bytes(out)
