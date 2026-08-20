"""
SelectiveReconstructor — contract section 9.

Acceptance:
- one-file reconstruction must not materialize the full snapshot
  (only the requested file's bytes, and its reference chain, are
  touched — no other file in the version is read or decoded);
- SHA-256 must pass before success;
- failures are explicit (typed errors, no silent fallback).
"""

from __future__ import annotations

import json

from .cas import ContentAddressableStore
from .core_adapter import CoreReconstructor, verify_or_raise
from .errors import FileNotFoundInVersion, KeyNotFoundInVersion, TemporalOrderError
from .models import FileEntry, ReconstructedFile, VersionManifest
from .temporal_index import TemporalIndex


class SelectiveReconstructor:
    def __init__(
        self,
        index: TemporalIndex,
        cas: ContentAddressableStore,
        core: CoreReconstructor,
    ):
        self._index = index
        self._cas = cas
        self._core = core
        # Every Evidence returned by the index is resolved through a real
        # reconstruction + SHA verification, never CAS-presence alone.
        from .evidence import EvidenceResolver
        self._evidence_resolver = EvidenceResolver(index, self)
        self._index.bind_evidence_resolver(self._evidence_resolver)

    def _find_entry(self, manifest: VersionManifest, file_path: str) -> FileEntry:
        for entry in manifest.files:
            if entry.path == file_path:
                return entry
        raise FileNotFoundInVersion(manifest.version_id, file_path)

    def _resolve_reference_bytes(self, entry: FileEntry) -> bytes | None:
        """Resolve the reference lineage iteratively.

        This avoids Python recursion-depth failures on long version chains and
        detects reference cycles explicitly. Only the requested file lineage is
        touched; unrelated files are never materialized.
        """
        if entry.reference_version_id is None:
            return None

        chain: list[FileEntry] = []
        current = entry
        visited: set[tuple[str, str]] = set()

        while current.reference_version_id is not None:
            ref_version = current.reference_version_id
            marker = (ref_version, entry.path)
            if marker in visited:
                raise TemporalOrderError(
                    f"reference cycle detected for {entry.path!r} at version {ref_version!r}"
                )
            visited.add(marker)

            ref_manifest = self._index.get_manifest(ref_version)
            ref_entry = self._find_entry(ref_manifest, entry.path)
            chain.append(ref_entry)
            current = ref_entry

        reference_bytes: bytes | None = None
        for ref_entry in reversed(chain):
            ref_representation = self._cas.get(ref_entry.representation_ref)
            reference_bytes = self._core.reconstruct(reference_bytes, ref_representation)

        return reference_bytes

    def reconstruct_file(self, version_id: str, file_path: str) -> ReconstructedFile:
        manifest = self._index.get_manifest(version_id)
        entry = self._find_entry(manifest, file_path)

        representation = self._cas.get(entry.representation_ref)
        reference_bytes = self._resolve_reference_bytes(entry)
        data = self._core.reconstruct(reference_bytes, representation)

        verify_or_raise(
            self._core, data, entry.sha256,
            context=f"{version_id}:{file_path}",
        )

        return ReconstructedFile(
            version_id=version_id,
            file_path=file_path,
            bytes_data=data,
            sha256=entry.sha256,
            verification_passed=True,
        )

    def reconstruct_key(self, version_id: str, file_path: str, key_path: str):
        reconstructed = self.reconstruct_file(version_id, file_path)
        value = json.loads(reconstructed.bytes_data)
        node = value
        for part in [] if key_path in ("", ".") else key_path.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                raise KeyNotFoundInVersion(version_id, file_path, key_path)
        return node
