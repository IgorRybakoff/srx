"""Evidence resolution for exact historical sources.

An Evidence object is not considered verified merely because its representation
exists in CAS. Resolution reconstructs the historical artifact through the
public SRX core path and verifies SHA-256 before returning a verified record.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from .errors import InvalidEvidence, VersionNotFound, FileNotFoundInVersion
from .models import Evidence

if TYPE_CHECKING:
    from .reconstructor import SelectiveReconstructor
    from .temporal_index import TemporalIndex


class EvidenceResolver:
    def __init__(self, index: "TemporalIndex", reconstructor: "SelectiveReconstructor"):
        self._index = index
        self._reconstructor = reconstructor

    def _source_version(self, evidence: Evidence) -> str:
        """Return the version whose exact file bytes prove this evidence.

        Normal changes are proven by the event version itself. A deletion has no
        file in the event version, so its parent artifact is the exact source
        that proves what was deleted.
        """
        manifest = self._index.get_manifest(evidence.version_id)
        if any(f.path == evidence.file_path for f in manifest.files):
            return evidence.version_id

        if evidence.change_type == "deleted":
            for parent_id in manifest.parent_ids:
                parent = self._index.get_manifest(parent_id)
                if any(f.path == evidence.file_path for f in parent.files):
                    return parent_id

        raise InvalidEvidence(
            f"no reconstructable source for {evidence.version_id}:{evidence.file_path}"
        )

    def resolve(self, evidence: Evidence) -> Evidence:
        if not evidence.source_sha256:
            raise InvalidEvidence(
                f"missing source hash for {evidence.version_id}:{evidence.file_path}"
            )

        try:
            source_version = self._source_version(evidence)
            restored = self._reconstructor.reconstruct_file(
                source_version, evidence.file_path
            )
        except (VersionNotFound, FileNotFoundInVersion) as exc:
            raise InvalidEvidence(str(exc)) from exc

        if not restored.verification_passed:
            raise InvalidEvidence(
                f"source failed verification for {source_version}:{evidence.file_path}"
            )
        if restored.sha256 != evidence.source_sha256:
            raise InvalidEvidence(
                "evidence hash does not match exact reconstructed source: "
                f"expected {evidence.source_sha256}, got {restored.sha256}"
            )

        # reconstructed_path is intentionally None for in-memory reconstruction.
        # The exact bytes are available through SelectiveReconstructor using the
        # same version/file evidence tuple.
        return replace(evidence, verification_passed=True)
