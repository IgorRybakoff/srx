"""
Minimal content-addressable store (CAS).

This is temporal-layer plumbing only — it is NOT part of srx-core and
does not implement any SRX transformation/residual algorithm. It exists
so the temporal layer has somewhere to persist the byte payloads that
srx-core's public interfaces would otherwise produce/consume.

representation_ref values produced here have the form "sha256:<hex>".
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .errors import CorruptRepresentation, MissingReference

REF_PREFIX = "sha256:"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ContentAddressableStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, digest: str) -> Path:
        return self.root / digest[:2] / digest[2:]

    def put(self, data: bytes) -> str:
        digest = sha256_hex(data)
        path = self._path_for(digest)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(data)
        return f"{REF_PREFIX}{digest}"

    def exists(self, ref: str) -> bool:
        if not ref.startswith(REF_PREFIX):
            return False
        digest = ref[len(REF_PREFIX):]
        return self._path_for(digest).exists()

    def get(self, ref: str) -> bytes:
        if not ref.startswith(REF_PREFIX):
            raise CorruptRepresentation(ref, "unrecognized reference scheme")
        digest = ref[len(REF_PREFIX):]
        path = self._path_for(digest)
        if not path.exists():
            raise MissingReference(ref)
        data = path.read_bytes()
        actual = sha256_hex(data)
        if actual != digest:
            # CAS content does not match its own key -> corrupt on disk.
            raise CorruptRepresentation(ref, f"stored content hash {actual} != key")
        return data
