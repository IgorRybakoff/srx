"""Tests for SRXReconstructor and SRXVerifier."""

import unittest
from srx.adapters.json_adapter import JSONAdapter
from srx.core.constants import REC_SNAPSHOT, REC_STRUCT
from srx.core.evaluate import evaluate_structural
from srx.core.record import create_record, encode_structural_payload
from srx.core.varint import sha256_hex
from srx.reconstruct.reconstructor import SRXReconstructor
from srx.reconstruct.verifier import SRXVerifier


class TestReconstructionAndVerification(unittest.TestCase):
    """Verify exact round-trip reconstruction and cryptographic verification."""

    def test_reconstruct_structural_record(self) -> None:
        ref_obj = {"service": "gateway", "port": 8080, "routes": ["/auth", "/api"]}
        tgt_obj = {"service": "gateway", "port": 8443, "routes": ["/auth", "/api", "/metrics"], "ssl": True}
        
        ref_bytes = JSONAdapter.serialize(ref_obj, pretty=True)
        tgt_bytes = JSONAdapter.serialize(tgt_obj, pretty=True)

        best, _ = evaluate_structural(ref_bytes, tgt_bytes)
        inner = encode_structural_payload(
            best["transform_blob"],
            best["residual_type"],
            best["residual_blob"],
        )
        record = create_record(ref_bytes, tgt_bytes, REC_STRUCT, inner)

        # Reconstruct
        reconstructed = SRXReconstructor.reconstruct(ref_bytes, record)
        self.assertEqual(reconstructed, tgt_bytes)
        self.assertEqual(sha256_hex(reconstructed), sha256_hex(tgt_bytes))

        # Verify
        evidence = SRXVerifier.verify_record(ref_bytes, record)
        self.assertTrue(evidence["verified"])
        self.assertEqual(evidence["expected_target_hash"], sha256_hex(tgt_bytes))
        self.assertEqual(evidence["record_type"], "STRUCTURAL")

    def test_reconstruct_snapshot_record(self) -> None:
        tgt_bytes = b'{"status": "ok", "timestamp": 1234567890}\n'
        from srx.core.compression import zstd
        compressed = zstd(tgt_bytes)
        record = create_record(None, tgt_bytes, REC_SNAPSHOT, compressed)

        reconstructed = SRXReconstructor.reconstruct(None, record)
        self.assertEqual(reconstructed, tgt_bytes)

        evidence = SRXVerifier.verify_record(None, record)
        self.assertTrue(evidence["verified"])
        self.assertEqual(evidence["record_type"], "SNAPSHOT")

    def test_reconstruct_tampered_payload_fails(self) -> None:
        ref_bytes = b'{"a": 1}\n'
        tgt_bytes = b'{"a": 2}\n'
        best, _ = evaluate_structural(ref_bytes, tgt_bytes)
        inner = encode_structural_payload(
            best["transform_blob"],
            best["residual_type"],
            best["residual_blob"],
        )
        record = bytearray(create_record(ref_bytes, tgt_bytes, REC_STRUCT, inner))
        
        # Tamper with target hash in header
        record[40] ^= 0xFF
        with self.assertRaises(Exception):
            SRXReconstructor.reconstruct(ref_bytes, bytes(record))


if __name__ == "__main__":
    unittest.main()
