"""
LocalFolderConnector — v0.1 priority connector #1.

Treats a sequence of registered directory snapshots as ordered
versions. Each snapshot is a plain directory on disk; the connector
itself assigns no meaning to filenames beyond relative paths.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

from ..errors import VersionNotFound


class LocalFolderConnector:
    def __init__(self):
        # version_id -> (root_path, timestamp)
        self._snapshots: dict[str, tuple[Path, str]] = {}
        self._order: list[str] = []

    def register_snapshot(
        self,
        version_id: str,
        root: str | Path,
        timestamp: str | None = None,
    ) -> None:
        if version_id in self._snapshots:
            raise ValueError(f"snapshot {version_id!r} already registered")
        ts = timestamp or _dt.datetime.now(_dt.timezone.utc).isoformat()
        self._snapshots[version_id] = (Path(root), ts)
        self._order.append(version_id)

    def list_versions(self) -> list[str]:
        return list(self._order)

    def _root(self, version_id: str) -> Path:
        try:
            return self._snapshots[version_id][0]
        except KeyError:
            raise VersionNotFound(version_id) from None

    def list_files(self, version_id: str) -> list[str]:
        root = self._root(version_id)
        files = [
            str(p.relative_to(root)).replace("\\", "/")
            for p in sorted(root.rglob("*"))
            if p.is_file()
        ]
        return files

    def read_file(self, version_id: str, path: str) -> bytes:
        root = self._root(version_id)
        return (root / path).read_bytes()

    def version_timestamp(self, version_id: str) -> str:
        try:
            return self._snapshots[version_id][1]
        except KeyError:
            raise VersionNotFound(version_id) from None
