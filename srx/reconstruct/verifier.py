"""Cryptographic verification engine for SRX Public v0.1 records."""

from srx.core.constants import REC_BSDIFF, REC_SNAPSHOT, REC_STRUCT, REC_ZSTD_PATCH
from srx.core.record import parse_record
from srx.core.varint import sha256, sha256_hex
from srx.reconstruct.reconstructor import SRXReconstructor

RECORD_TYPE_NAMES = {
    REC_SNAPSHOT: "SNAPSHOT",
    REC_ZSTD_PATCH: "ZSTD_PATCH",
    REC_BSDIFF: "BSDIFF",
    REC_STRUCT: "STRUCTURAL",
}


class SRXVerifier:
    """Verifier for exact reconstructed artifacts and SRX binary records."""

    @staticmethod
    def verify(reconstructed: bytes, expected_hash_hex: str) -> bool:
        """Verify that SHA-256 digest of reconstructed bytes matches expected hash."""
        return sha256_hex(reconstructed).lower() == expected_hash_hex.strip().lower()

    @staticmethod
    def verify_record(ref: bytes | None, record: bytes) -> dict:
        """Parse, reconstruct, and verify an SRX record, returning full provenance evidence."""
        parsed = parse_record(record)
        expected_ref_hex = parsed["ref_hash"].hex()
        expected_tgt_hex = parsed["target_hash"].hex()
        record_type_name = RECORD_TYPE_NAMES.get(parsed["record_type"], f"UNKNOWN({parsed['record_type']})")
        
        try:
            reconstructed = SRXReconstructor.reconstruct(ref, record)
            actual_tgt_hex = sha256_hex(reconstructed)
            is_valid = actual_tgt_hex == expected_tgt_hex and len(reconstructed) == parsed["target_size"]
            
            return {
                "verified": is_valid,
                "record_type": record_type_name,
                "record_bytes": len(record),
                "target_size_bytes": len(reconstructed),
                "expected_target_hash": expected_tgt_hex,
                "actual_target_hash": actual_tgt_hex,
                "reference_hash": expected_ref_hex,
                "error": None,
                "reconstructed_bytes": reconstructed,
            }
        except Exception as e:
            return {
                "verified": False,
                "record_type": record_type_name,
                "record_bytes": len(record),
                "target_size_bytes": parsed["target_size"],
                "expected_target_hash": expected_tgt_hex,
                "actual_target_hash": None,
                "reference_hash": expected_ref_hex,
                "error": str(e),
                "reconstructed_bytes": None,
            }
