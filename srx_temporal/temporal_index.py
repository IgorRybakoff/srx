"""
TemporalIndex — contract section 8.

Rules enforced here:
- deterministic causal order by committed DAG/insertion sequence;
- timestamps are metadata and never invert parent -> child order;
- no LLM;
- missing objects return explicit typed errors;
- no silent best-effort fallback.
"""

from __future__ import annotations

from .cas import ContentAddressableStore
from .errors import TemporalOrderError, VersionNotFound
from .models import (
    Evidence,
    FileChange,
    StructuralChange,
    TemporalHit,
    VersionManifest,
)


def _sort_key(manifest: VersionManifest) -> tuple[str, str]:
    return (manifest.timestamp, manifest.version_id)


class TemporalIndex:
    def __init__(self, cas: ContentAddressableStore):
        self._cas = cas
        self._evidence_resolver = None
        self._manifests: dict[str, VersionManifest] = {}
        self._file_changes: dict[str, list[FileChange]] = {}
        self._structural_changes: dict[str, list[StructuralChange]] = {}
        self._order: list[str] = []  # version_ids in insertion order


    def bind_evidence_resolver(self, resolver) -> None:
        """Bind the verifier used before Evidence leaves the index.

        The resolver is deliberately injected after construction to avoid a
        dependency cycle between TemporalIndex and SelectiveReconstructor.
        """
        self._evidence_resolver = resolver

    # -- writes ------------------------------------------------------

    def add_version(
        self,
        manifest: VersionManifest,
        file_changes: list[FileChange],
        structural_changes: list[StructuralChange],
    ) -> None:
        if manifest.version_id in self._manifests:
            raise TemporalOrderError(
                f"version {manifest.version_id!r} already committed (immutable)"
            )
        for parent_id in manifest.parent_ids:
            if parent_id not in self._manifests:
                raise TemporalOrderError(
                    f"parent {parent_id!r} of {manifest.version_id!r} "
                    f"has not been committed yet"
                )
        for fc in file_changes:
            if fc.version_id != manifest.version_id:
                raise TemporalOrderError(
                    f"FileChange.version_id {fc.version_id!r} does not match "
                    f"manifest {manifest.version_id!r}"
                )
        for sc in structural_changes:
            if sc.version_id != manifest.version_id:
                raise TemporalOrderError(
                    f"StructuralChange.version_id {sc.version_id!r} does not "
                    f"match manifest {manifest.version_id!r}"
                )

        self._manifests[manifest.version_id] = manifest
        self._file_changes[manifest.version_id] = list(file_changes)
        self._structural_changes[manifest.version_id] = list(structural_changes)
        self._order.append(manifest.version_id)

    # -- reads ---------------------------------------------------------

    def get_manifest(self, version_id: str) -> VersionManifest:
        try:
            return self._manifests[version_id]
        except KeyError:
            raise VersionNotFound(version_id) from None

    def list_versions(self) -> list[VersionManifest]:
        # Parents must be committed before children in add_version(), so
        # insertion order is a deterministic topological/causal order.
        # Wall-clock timestamps are metadata only: clock skew or backdated
        # commits must never make a child appear before its parent.
        return [self._manifests[version_id] for version_id in self._order]

    def _build_evidence(
        self,
        manifest: VersionManifest,
        file_path: str,
        key_path: str | None,
        change_type: str,
        previous_value_ref: str | None,
        current_value_ref: str | None,
    ) -> Evidence:
        entry = next((f for f in manifest.files if f.path == file_path), None)
        # A deletion has no file in the event manifest. Its previous hash is
        # therefore the exact source hash and EvidenceResolver reconstructs the
        # parent artifact before the hit is returned.
        source_sha256 = entry.sha256 if entry is not None else (previous_value_ref or "")

        evidence = Evidence(
            version_id=manifest.version_id,
            timestamp=manifest.timestamp,
            file_path=file_path,
            key_path=key_path,
            source_sha256=source_sha256,
            reconstructed_path=None,
            verification_passed=False,
            change_type=change_type,
            previous_value_ref=previous_value_ref,
            current_value_ref=current_value_ref,
        )
        if self._evidence_resolver is None:
            return evidence
        return self._evidence_resolver.resolve(evidence)

    def timeline_by_file(self, path: str) -> list[TemporalHit]:
        hits: list[TemporalHit] = []
        for version_id in self._order:
            manifest = self._manifests[version_id]
            for fc in self._file_changes[version_id]:
                if fc.path != path and fc.old_path != path:
                    continue
                evidence = self._build_evidence(
                    manifest=manifest,
                    file_path=fc.path,
                    key_path=None,
                    change_type=fc.change_type.value,
                    previous_value_ref=fc.old_sha256,
                    current_value_ref=fc.new_sha256,
                )
                hits.append(
                    TemporalHit(
                        version_id=version_id,
                        timestamp=manifest.timestamp,
                        file_path=fc.path,
                        key_path=None,
                        change_type=fc.change_type.value,
                        evidence=evidence,
                    )
                )
        # Preserve committed causal order. Do not re-sort by timestamp: a
        # backdated child must never appear before its parent.
        return hits

    def timeline_by_key(
        self,
        key_path: str,
        *,
        file_path: str | None = None,
    ) -> list[TemporalHit]:
        hits: list[TemporalHit] = []
        for version_id in self._order:
            manifest = self._manifests[version_id]
            for sc in self._structural_changes[version_id]:
                if sc.key_path != key_path:
                    continue
                if file_path is not None and sc.file_path != file_path:
                    continue
                evidence = self._build_evidence(
                    manifest=manifest,
                    file_path=sc.file_path,
                    key_path=sc.key_path,
                    change_type=sc.change_type.value,
                    previous_value_ref=sc.old_value_ref,
                    current_value_ref=sc.new_value_ref,
                )
                hits.append(
                    TemporalHit(
                        version_id=version_id,
                        timestamp=manifest.timestamp,
                        file_path=sc.file_path,
                        key_path=sc.key_path,
                        change_type=sc.change_type.value,
                        evidence=evidence,
                    )
                )
        # Preserve committed causal order. Do not re-sort by timestamp.
        return hits

    def diff_versions(
        self,
        v1: str,
        v2: str,
        *,
        file_path: str | None = None,
    ) -> dict:
        m1 = self.get_manifest(v1)
        m2 = self.get_manifest(v2)

        files1 = {f.path: f for f in m1.files if file_path is None or f.path == file_path}
        files2 = {f.path: f for f in m2.files if file_path is None or f.path == file_path}

        added = sorted(set(files2) - set(files1))
        removed = sorted(set(files1) - set(files2))
        common = set(files1) & set(files2)
        modified = sorted(p for p in common if files1[p].sha256 != files2[p].sha256)
        unchanged = sorted(p for p in common if files1[p].sha256 == files2[p].sha256)

        structural = [
            sc for sc in self._structural_changes.get(v2, [])
            if file_path is None or sc.file_path == file_path
        ]

        return {
            "from_version": v1,
            "to_version": v2,
            "files_added": added,
            "files_removed": removed,
            "files_modified": modified,
            "files_unchanged": unchanged,
            "structural_changes": [sc.__dict__ for sc in structural],
        }
