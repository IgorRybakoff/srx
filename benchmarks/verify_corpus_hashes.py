"""Verify frozen benchmark corpus SHA-256 hashes."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HASH_FILE = ROOT / "benchmarks" / "FROZEN_CORPUS_SHA256.txt"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    failures = []
    checked = 0
    for raw in HASH_FILE.read_text().splitlines():
        line = raw.strip()
        if not line:
            continue
        expected, rel = line.split(maxsplit=1)
        path = ROOT / rel
        actual = sha256(path)
        checked += 1
        if actual != expected:
            failures.append((rel, expected, actual))

    if failures:
        for rel, expected, actual in failures:
            print(f"FAIL {rel}\n  expected: {expected}\n  actual:   {actual}")
        return 1

    print(f"PASS: {checked} frozen corpus files match SHA-256 manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
