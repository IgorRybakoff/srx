"""Stable public facade for SRX Public v0.1.

This module exposes deterministic encode/reconstruct/verify operations used by
higher product layers such as temporal/evidence indexing. The implementation
reuses the frozen v0.9 algorithms and does not alter benchmark semantics.
"""

from srx.core.compression import zpatch, zstd
from srx.core.constants import REC_BSDIFF, REC_SNAPSHOT, REC_STRUCT, REC_ZSTD_PATCH
from srx.core.evaluate import evaluate_structural
from srx.core.record import (
    create_record,
    encode_structural_payload,
    parse_record,
)
from srx.reconstruct.reconstructor import SRXReconstructor
from srx.reconstruct.verifier import SRXVerifier


class SRXCoreAPI:
    """Minimal deterministic API consumed by temporal/evidence layers."""

    @staticmethod
    def encode(reference: bytes | None, target: bytes) -> bytes:
        """Encode *target* as the cheapest exact SRX record available.

        Selection policy mirrors the frozen v0.9 benchmark gate:
        conventional snapshot/patch candidates compete with structural
        representation; structural wins only when physically smaller.
        Ties therefore remain conventional.
        """
        snapshot = create_record(None, target, REC_SNAPSHOT, zstd(target))
        candidates: list[tuple[int, int, bytes]] = [
            (len(snapshot), 0, snapshot),  # conventional priority on ties
        ]

        if reference is not None:
            patch = create_record(reference, target, REC_ZSTD_PATCH, zpatch(reference, target))
            candidates.append((len(patch), 0, patch))

            # Structural evaluation is currently defined for JSON. If the
            # adapter cannot parse the content, the conventional candidates
            # remain authoritative and exact.
            try:
                best, _ = evaluate_structural(reference, target)
                inner = encode_structural_payload(
                    best["transform_blob"],
                    best["residual_type"],
                    best["residual_blob"],
                )
                structural = create_record(reference, target, REC_STRUCT, inner)
                candidates.append((len(structural), 1, structural))
            except (ValueError, TypeError, UnicodeDecodeError):
                pass

        return min(candidates, key=lambda item: (item[0], item[1]))[2]

    @staticmethod
    def requires_reference(representation: bytes) -> bool:
        parsed = parse_record(representation)
        return parsed["record_type"] in {REC_ZSTD_PATCH, REC_BSDIFF, REC_STRUCT}

    @staticmethod
    def reconstruct(reference: bytes | None, representation: bytes) -> bytes:
        return SRXReconstructor.reconstruct(reference, representation)

    @staticmethod
    def verify(reconstructed: bytes, expected_sha256: str) -> bool:
        return SRXVerifier.verify(reconstructed, expected_sha256)
