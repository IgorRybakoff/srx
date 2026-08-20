"""
Immutable data model for the SRX Public v0.1 temporal/evidence layer.

All records are immutable (frozen dataclasses). A VersionManifest is
immutable once committed to a TemporalIndex.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# --- 2. Identifiers ---------------------------------------------------

VersionId = str
Sha256Hex = str
FilePath = str
KeyPath = str
Timestamp = str  # ISO-8601, offset-aware


# --- 3. VersionManifest -------------------------------------------------

@dataclass(frozen=True)
class FileEntry:
    path: FilePath
    sha256: Sha256Hex
    size_bytes: int
    media_type: str | None
    representation_ref: str
    reference_version_id: VersionId | None


@dataclass(frozen=True)
class VersionManifest:
    version_id: VersionId
    timestamp: Timestamp
    parent_ids: tuple[VersionId, ...]
    message: str | None
    files: tuple[FileEntry, ...]


# --- 4. FileChange -------------------------------------------------------

class FileChangeType(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass(frozen=True)
class FileChange:
    version_id: VersionId
    timestamp: Timestamp
    path: FilePath
    change_type: FileChangeType
    old_path: FilePath | None
    old_sha256: Sha256Hex | None
    new_sha256: Sha256Hex | None
    old_size_bytes: int | None
    new_size_bytes: int | None


# --- 5. StructuralChange --------------------------------------------------

class StructuralChangeType(str, Enum):
    KEY_ADDED = "key_added"
    KEY_REMOVED = "key_removed"
    VALUE_CHANGED = "value_changed"
    TYPE_CHANGED = "type_changed"
    MOVED = "moved"
    REORDERED = "reordered"


@dataclass(frozen=True)
class StructuralChange:
    version_id: VersionId
    timestamp: Timestamp
    file_path: FilePath
    key_path: KeyPath
    change_type: StructuralChangeType
    old_value_ref: str | None
    new_value_ref: str | None
    transformation_kind: str | None


# --- 6. Evidence -----------------------------------------------------------

@dataclass(frozen=True)
class Evidence:
    version_id: VersionId
    timestamp: Timestamp
    file_path: FilePath
    key_path: KeyPath | None
    source_sha256: Sha256Hex
    reconstructed_path: str | None
    verification_passed: bool
    change_type: str | None
    previous_value_ref: str | None
    current_value_ref: str | None


# --- 7. TemporalHit ----------------------------------------------------

@dataclass(frozen=True)
class TemporalHit:
    version_id: VersionId
    timestamp: Timestamp
    file_path: FilePath
    key_path: KeyPath | None
    change_type: str
    evidence: Evidence


# --- 9. ReconstructedFile (contract section 9) --------------------------

@dataclass(frozen=True)
class ReconstructedFile:
    version_id: VersionId
    file_path: FilePath
    bytes_data: bytes
    sha256: Sha256Hex
    verification_passed: bool
