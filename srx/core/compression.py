"""Compression and byte-level delta patch backends for SRX Public v0.1.

Supports zstd/zlib compression and exact binary patch/unpatch routines.
"""

import bz2
import difflib
import os
import shutil
import struct
import subprocess
import tempfile
import zlib


def _has_zstd() -> bool:
    return shutil.which("zstd") is not None


def zstd(data: bytes, level: int = 19) -> bytes:
    """Compress data using zstd if available, falling back to zlib (level 9)."""
    if _has_zstd():
        with tempfile.TemporaryDirectory() as td:
            a = os.path.join(td, "a")
            o = os.path.join(td, "o.zst")
            with open(a, "wb") as f:
                f.write(data)
            subprocess.run(["zstd", f"-{level}", "-q", "-f", a, "-o", o], check=True)
            with open(o, "rb") as f:
                return f.read()
    return b"\x78\xda" + zlib.compress(data, 9)[2:]


def unzstd(data: bytes) -> bytes:
    """Decompress data using zstd if available or zlib fallback."""
    if _has_zstd() and data[:4] == b"\x28\xb5\x2f\xfd":
        with tempfile.TemporaryDirectory() as td:
            a = os.path.join(td, "a.zst")
            o = os.path.join(td, "o")
            with open(a, "wb") as f:
                f.write(data)
            subprocess.run(["zstd", "-d", "-q", "-f", a, "-o", o], check=True)
            with open(o, "rb") as f:
                return f.read()
    try:
        return zlib.decompress(data)
    except Exception:
        return zlib.decompress(data, -zlib.MAX_WBITS)


def zpatch(base: bytes, target: bytes) -> bytes:
    """Compute exact byte patch from base to target."""
    if _has_zstd():
        with tempfile.TemporaryDirectory() as td:
            a = os.path.join(td, "a")
            b = os.path.join(td, "b")
            p = os.path.join(td, "p")
            with open(a, "wb") as f:
                f.write(base)
            with open(b, "wb") as f:
                f.write(target)
            res = subprocess.run(
                ["zstd", "-19", f"--patch-from={a}", "-q", "-f", b, "-o", p],
                capture_output=True,
            )
            if res.returncode == 0:
                with open(p, "rb") as f:
                    return f.read()

    # Portable exact binary patch fallback
    matcher = difflib.SequenceMatcher(None, base, target, autojunk=False)
    ops = matcher.get_opcodes()
    patch_body = bytearray()
    patch_body += struct.pack(">I", len(target))
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            continue
        patch_body += tag[0].encode("ascii")
        patch_body += struct.pack(">IIII", i1, i2, j1, j2)
        if tag in ("insert", "replace"):
            patch_body += target[j1:j2]
    return b"SRXP1" + zlib.compress(bytes(patch_body), 9)


def unzpatch(base: bytes, patch: bytes) -> bytes:
    """Apply exact byte patch against base."""
    if patch.startswith(b"SRXP1"):
        decomp = zlib.decompress(patch[5:])
        tgt_len = struct.unpack(">I", decomp[:4])[0]
        offset = 4
        out = bytearray(base)
        # Apply delta chunks
        chunks: list[tuple[str, int, int, bytes]] = []
        while offset < len(decomp):
            tag_char = chr(decomp[offset])
            offset += 1
            i1, i2, j1, j2 = struct.unpack(">IIII", decomp[offset : offset + 16])
            offset += 16
            extra = b""
            if tag_char in ("i", "r"):
                length = j2 - j1
                extra = decomp[offset : offset + length]
                offset += length
            chunks.append((tag_char, i1, i2, extra))
        
        # Build reconstructed target
        res = bytearray()
        last_i = 0
        for tag_char, i1, i2, extra in chunks:
            res += base[last_i:i1]
            if tag_char in ("i", "r"):
                res += extra
            last_i = i2
        res += base[last_i:]
        out_bytes = bytes(res)
        if len(out_bytes) != tgt_len:
            raise ValueError(f"Patch target length mismatch: got {len(out_bytes)}, expected {tgt_len}")
        return out_bytes

    if _has_zstd():
        with tempfile.TemporaryDirectory() as td:
            a = os.path.join(td, "a")
            p = os.path.join(td, "p")
            o = os.path.join(td, "o")
            with open(a, "wb") as f:
                f.write(base)
            with open(p, "wb") as f:
                f.write(patch)
            subprocess.run(["zstd", "-d", f"--patch-from={a}", "-q", "-f", p, "-o", o], check=True)
            with open(o, "rb") as f:
                return f.read()

    raise ValueError("Unsupported patch format or missing zstd tool")


def bspatch(base: bytes, patch: bytes) -> bytes:
    """Apply bsdiff-format patch to base buffer."""
    if patch[:16] != b"ENDSLEY/BSDIFF43":
        raise ValueError("Invalid BSDIFF patch magic header")

    def offtin(buf: bytes) -> int:
        y = buf[7] & 0x7F
        for k in range(6, -1, -1):
            y = y * 256 + buf[k]
        return -y if buf[7] & 0x80 else y

    newsize = offtin(patch[16:24])
    stream = bz2.decompress(patch[24:])
    i = 0
    oldpos = 0
    out = bytearray()
    while len(out) < newsize:
        c0 = offtin(stream[i : i + 8])
        c1 = offtin(stream[i + 8 : i + 16])
        c2 = offtin(stream[i + 16 : i + 24])
        i += 24
        diff = stream[i : i + c0]
        i += c0
        for j, q in enumerate(diff):
            op = oldpos + j
            out.append((q + (base[op] if 0 <= op < len(base) else 0)) & 255)
        oldpos += c0
        out += stream[i : i + c1]
        i += c1
        oldpos += c2
    return bytes(out[:newsize])
