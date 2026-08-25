"""Persistence adapter for the SRX temporal/evidence layer.

This module serializes and restores the existing ``TemporalIndex`` without
replacing its invariants or duplicating its business logic. The on-disk
manifest stores immutable temporal metadata only; representation bytes remain
in the existing content-addressable store at ``<store>/cas``.

Evidence is intentionally not persisted as trusted state. After reload,
``SelectiveReconstructor`` re-binds ``EvidenceResolver`` and evidence queries
perform exact reconstruction + SHA-256 verification again.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .cas import ContentAddressableStore
from .models import (
    FileChange,
    FileChangeType,
    FileEntry,
    StructuralChange,
    StructuralChangeType,
    VersionManifest,
)
from .temporal_index import TemporalIndex


MANIFEST_FILENAME = "temporal_manifest.json"
FORMAT_VERSION = 1


def _serialize_file_entry(entry: FileEntry) -> dict[str, Any]:
    return {
        "path": entry.path,
        "sha256": entry.sha256,
        "size_bytes": entry.size_bytes,
        "media_type": entry.media_type,
        "representation_ref": entry.representation_ref,
        "reference_version_id": entry.reference_version_id,
    }


def _deserialize_file_entry(data: dict[str, Any]) -> FileEntry:
    return FileEntry(
        path=data["path"],
        sha256=data["sha256"],
        size_bytes=data["size_bytes"],
        media_type=data.get("media_type"),
        representation_ref=data["representation_ref"],
        reference_version_id=data.get("reference_version_id"),
    )


def _serialize_manifest(manifest: VersionManifest) -> dict[str, Any]:
    return {
        "version_id": manifest.version_id,
        "timestamp": manifest.timestamp,
        "parent_ids": list(manifest.parent_ids),
        "message": manifest.message,
        "files": [_serialize_file_entry(entry) for entry in manifest.files],
    }


def _deserialize_manifest(data: dict[str, Any]) -> VersionManifest:
    return VersionManifest(
        version_id=data["version_id"],
        timestamp=data["timestamp"],
        parent_ids=tuple(data.get("parent_ids", [])),
        message=data.get("message"),
        files=tuple(_deserialize_file_entry(entry) for entry in data.get("files", [])),
    )


def _serialize_file_change(change: FileChange) -> dict[str, Any]:
    return {
        "version_id": change.version_id,
        "timestamp": change.timestamp,
        "path": change.path,
        "change_type": change.change_type.value,
        "old_path": change.old_path,
        "old_sha256": change.old_sha256,
        "new_sha256": change.new_sha256,
        "old_size_bytes": change.old_size_bytes,
        "new_size_bytes": change.new_size_bytes,
    }


def _deserialize_file_change(data: dict[str, Any]) -> FileChange:
    return FileChange(
        version_id=data["version_id"],
        timestamp=data["timestamp"],
        path=data["path"],
        change_type=FileChangeType(data["change_type"]),
        old_path=data.get("old_path"),
        old_sha256=data.get("old_sha256"),
        new_sha256=data.get("new_sha256"),
        old_size_bytes=data.get("old_size_bytes"),
        new_size_bytes=data.get("new_size_bytes"),
    )


def _serialize_structural_change(change: StructuralChange) -> dict[str, Any]:
    return {
        "version_id": change.version_id,
        "timestamp": change.timestamp,
        "file_path": change.file_path,
        "key_path": change.key_path,
        "change_type": change.change_type.value,
        "old_value_ref": change.old_value_ref,
        "new_value_ref": change.new_value_ref,
        "transformation_kind": change.transformation_kind,
    }


def _deserialize_structural_change(data: dict[str, Any]) -> StructuralChange:
    return StructuralChange(
        version_id=data["version_id"],
        timestamp=data["timestamp"],
        file_path=data["file_path"],
        key_path=data["key_path"],
        change_type=StructuralChangeType(data["change_type"]),
        old_value_ref=data.get("old_value_ref"),
        new_value_ref=data.get("new_value_ref"),
        transformation_kind=data.get("transformation_kind"),
    )


def save_index(index: TemporalIndex, store_path: Path) -> Path:
    """Atomically persist ``index`` into ``store_path``.

    The manifest contains metadata and CAS references only. Actual SRX
    representations remain in ``<store>/cas``.
    """
    store_path = Path(store_path)
    store_path.mkdir(parents=True, exist_ok=True)
    manifest_path = store_path / MANIFEST_FILENAME

    versions: list[dict[str, Any]] = []
    for manifest, file_changes, structural_changes in index.iter_committed():
        versions.append(
            {
                "manifest": _serialize_manifest(manifest),
                "file_changes": [
                    _serialize_file_change(change) for change in file_changes
                ],
                "structural_changes": [
                    _serialize_structural_change(change)
                    for change in structural_changes
                ],
            }
        )

    payload = {
        "format_version": FORMAT_VERSION,
        "versions": versions,
    }

    tmp_path = manifest_path.with_name(manifest_path.name + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp_path, manifest_path)
    return manifest_path


def load_index(store_path: Path) -> TemporalIndex:
    """Restore a ``TemporalIndex`` from ``store_path``.

    Versions are re-committed through ``TemporalIndex.add_version`` in saved
    causal order, so parent-before-child and change/version invariants are
    validated again on every load.
    """
    store_path = Path(store_path)
    manifest_path = store_path / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"Temporal manifest not found: {manifest_path}")

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("format_version") != FORMAT_VERSION:
        raise ValueError(
            "Unsupported temporal manifest format version: "
            f"{payload.get('format_version')!r}"
        )

    versions_data = payload.get("versions")
    if not isinstance(versions_data, list):
        raise ValueError("Temporal manifest field 'versions' must be a list")

    cas = ContentAddressableStore(store_path / "cas")
    index = TemporalIndex(cas)

    for item in versions_data:
        if not isinstance(item, dict):
            raise ValueError("Temporal manifest version entry must be an object")
        manifest = _deserialize_manifest(item["manifest"])
        file_changes = [
            _deserialize_file_change(change)
            for change in item.get("file_changes", [])
        ]
        structural_changes = [
            _deserialize_structural_change(change)
            for change in item.get("structural_changes", [])
        ]
        index.add_version(manifest, file_changes, structural_changes)

    return index
