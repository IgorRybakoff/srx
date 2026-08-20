"""
Ingestion glue code for the demo/tests.

This module is temporal-layer ingestion plumbing, not the SRX core transformation detector.

The structural diff performed here is a deterministic recursive JSON
key-path index used only to populate StructuralChange records for temporal
queries/tests. It is NOT the SRX structural transformation detector and does
not participate in representation selection or cost optimization.
"""

from __future__ import annotations

import json

from .cas import ContentAddressableStore, sha256_hex
from .connectors.base import SourceConnector
from .errors import TemporalOrderError, VersionNotFound
from .models import (
    FileChange,
    FileChangeType,
    FileEntry,
    StructuralChange,
    StructuralChangeType,
    VersionManifest,
)
from .temporal_index import TemporalIndex
from .core_adapter import CoreCodec, StubCoreReconstructor
from .reconstructor import SelectiveReconstructor


def _guess_media_type(path: str) -> str | None:
    if path.endswith(".json"):
        return "application/json"
    return None


def _json_ref(value) -> str:
    """Canonical compact JSON used only as a small value reference in v0.1."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _join_key_path(parent: str, key: str) -> str:
    return key if not parent else f"{parent}.{key}"


def _leaf_changes_for_added(
    version_id: str,
    timestamp: str,
    file_path: str,
    key_path: str,
    value,
) -> list[StructuralChange]:
    if isinstance(value, dict) and value:
        out: list[StructuralChange] = []
        for key in sorted(value):
            out.extend(_leaf_changes_for_added(
                version_id, timestamp, file_path,
                _join_key_path(key_path, str(key)), value[key],
            ))
        return out
    return [StructuralChange(
        version_id=version_id, timestamp=timestamp, file_path=file_path,
        key_path=key_path, change_type=StructuralChangeType.KEY_ADDED,
        old_value_ref=None, new_value_ref=_json_ref(value),
        transformation_kind="recursive_json_diff_v0.1",
    )]


def _leaf_changes_for_removed(
    version_id: str,
    timestamp: str,
    file_path: str,
    key_path: str,
    value,
) -> list[StructuralChange]:
    if isinstance(value, dict) and value:
        out: list[StructuralChange] = []
        for key in sorted(value):
            out.extend(_leaf_changes_for_removed(
                version_id, timestamp, file_path,
                _join_key_path(key_path, str(key)), value[key],
            ))
        return out
    return [StructuralChange(
        version_id=version_id, timestamp=timestamp, file_path=file_path,
        key_path=key_path, change_type=StructuralChangeType.KEY_REMOVED,
        old_value_ref=_json_ref(value), new_value_ref=None,
        transformation_kind="recursive_json_diff_v0.1",
    )]


def _recursive_json_diff_values(
    version_id: str,
    timestamp: str,
    file_path: str,
    key_path: str,
    old_value,
    new_value,
) -> list[StructuralChange]:
    if type(old_value) is not type(new_value):
        return [StructuralChange(
            version_id=version_id, timestamp=timestamp, file_path=file_path,
            key_path=key_path, change_type=StructuralChangeType.TYPE_CHANGED,
            old_value_ref=_json_ref(old_value), new_value_ref=_json_ref(new_value),
            transformation_kind="recursive_json_diff_v0.1",
        )]

    if isinstance(old_value, dict):
        changes: list[StructuralChange] = []
        old_keys, new_keys = set(old_value), set(new_value)
        for key in sorted(new_keys - old_keys):
            changes.extend(_leaf_changes_for_added(
                version_id, timestamp, file_path,
                _join_key_path(key_path, str(key)), new_value[key],
            ))
        for key in sorted(old_keys - new_keys):
            changes.extend(_leaf_changes_for_removed(
                version_id, timestamp, file_path,
                _join_key_path(key_path, str(key)), old_value[key],
            ))
        for key in sorted(old_keys & new_keys):
            changes.extend(_recursive_json_diff_values(
                version_id, timestamp, file_path,
                _join_key_path(key_path, str(key)), old_value[key], new_value[key],
            ))
        return changes

    # Arrays are represented as one deterministic value at their key path in
    # v0.1. Sequence-aware structural transforms remain a core concern; the
    # temporal index only needs a stable queryable change record here.
    if old_value != new_value:
        return [StructuralChange(
            version_id=version_id, timestamp=timestamp, file_path=file_path,
            key_path=key_path, change_type=StructuralChangeType.VALUE_CHANGED,
            old_value_ref=_json_ref(old_value), new_value_ref=_json_ref(new_value),
            transformation_kind="recursive_json_diff_v0.1",
        )]
    return []


def _simple_json_structural_diff(
    version_id: str,
    timestamp: str,
    file_path: str,
    old_bytes: bytes | None,
    new_bytes: bytes,
) -> list[StructuralChange]:
    """Deterministic recursive JSON change index for temporal queries.

    This is not the SRX transformation detector and does not participate in
    representation selection. It only exposes nested key paths such as
    ``database.pool_size`` for historical queries.
    """
    try:
        new_value = json.loads(new_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []

    if not isinstance(new_value, dict):
        return []

    if old_bytes is None:
        changes: list[StructuralChange] = []
        for key in sorted(new_value):
            changes.extend(_leaf_changes_for_added(
                version_id, timestamp, file_path, str(key), new_value[key],
            ))
        return changes

    try:
        old_value = json.loads(old_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError):
        old_value = {}
    if not isinstance(old_value, dict):
        old_value = {}

    return _recursive_json_diff_values(
        version_id, timestamp, file_path, "", old_value, new_value,
    )


def ingest_snapshot(
    index: TemporalIndex,
    cas: ContentAddressableStore,
    connector: SourceConnector,
    version_id: str,
    parent_ids: tuple[str, ...] = (),
    message: str | None = None,
    core: CoreCodec | None = None,
) -> VersionManifest:
    """Ingest one snapshot into the temporal index.

    When a real CoreCodec is supplied, CAS stores canonical SRX record bytes
    produced by core.encode(). Unchanged file entries reuse the parent's
    representation. Isolated temporal tests may omit `core`, in which case the
    exact full-copy stub is used.
    """
    core = core or StubCoreReconstructor()
    timestamp = connector.version_timestamp(version_id)
    paths = connector.list_files(version_id)

    parent_manifest = None
    parent_id = parent_ids[0] if parent_ids else None
    if parent_ids:
        try:
            parent_manifest = index.get_manifest(parent_id)
        except VersionNotFound as exc:
            raise TemporalOrderError(
                f"cannot ingest {version_id!r}: parent {parent_id!r} "
                f"has not been committed yet"
            ) from exc
    parent_files = {f.path: f for f in parent_manifest.files} if parent_manifest else {}

    entries: list[FileEntry] = []
    file_changes: list[FileChange] = []
    structural_changes: list[StructuralChange] = []
    parent_reconstructor = SelectiveReconstructor(index, cas, core) if parent_manifest else None

    seen_paths = set()
    for path in paths:
        seen_paths.add(path)
        data = connector.read_file(version_id, path)
        digest = sha256_hex(data)
        prior = parent_files.get(path)

        if prior is not None and prior.sha256 == digest:
            # Same exact artifact: reuse the already stored SRX representation.
            entries.append(FileEntry(
                path=path,
                sha256=prior.sha256,
                size_bytes=prior.size_bytes,
                media_type=prior.media_type,
                representation_ref=prior.representation_ref,
                reference_version_id=prior.reference_version_id,
            ))
            continue

        old_data = None
        if prior is not None:
            assert parent_reconstructor is not None and parent_id is not None
            old_data = parent_reconstructor.reconstruct_file(parent_id, path).bytes_data

        representation = core.encode(old_data, data)
        representation_ref = cas.put(representation)
        reference_version_id = parent_id if (
            parent_id is not None and prior is not None and core.requires_reference(representation)
        ) else None

        entries.append(FileEntry(
            path=path,
            sha256=digest,
            size_bytes=len(data),
            media_type=_guess_media_type(path),
            representation_ref=representation_ref,
            reference_version_id=reference_version_id,
        ))

        if prior is None:
            file_changes.append(FileChange(
                version_id=version_id, timestamp=timestamp, path=path,
                change_type=FileChangeType.ADDED, old_path=None,
                old_sha256=None, new_sha256=digest,
                old_size_bytes=None, new_size_bytes=len(data),
            ))
            structural_changes += _simple_json_structural_diff(
                version_id, timestamp, path, None, data,
            )
        else:
            file_changes.append(FileChange(
                version_id=version_id, timestamp=timestamp, path=path,
                change_type=FileChangeType.MODIFIED, old_path=None,
                old_sha256=prior.sha256, new_sha256=digest,
                old_size_bytes=prior.size_bytes, new_size_bytes=len(data),
            ))
            structural_changes += _simple_json_structural_diff(
                version_id, timestamp, path, old_data, data,
            )

    for path, prior in parent_files.items():
        if path not in seen_paths:
            file_changes.append(FileChange(
                version_id=version_id, timestamp=timestamp, path=path,
                change_type=FileChangeType.DELETED, old_path=None,
                old_sha256=prior.sha256, new_sha256=None,
                old_size_bytes=prior.size_bytes, new_size_bytes=None,
            ))

    manifest = VersionManifest(
        version_id=version_id, timestamp=timestamp, parent_ids=parent_ids,
        message=message, files=tuple(entries),
    )
    index.add_version(manifest, file_changes, structural_changes)
    return manifest
