"""Reconstruction engine for SRX Public v0.1 records."""

from srx.adapters.json_adapter import JSONAdapter
from srx.core.codec import decode_transform
from srx.core.compression import bspatch, unzpatch, unzstd
from srx.core.constants import (
    REC_BSDIFF,
    REC_SNAPSHOT,
    REC_STRUCT,
    REC_ZSTD_PATCH,
    RES_FORMAT_GAPS,
    RES_NONE,
)
from srx.core.format_gaps import apply_format_gaps
from srx.core.ops import apply_ops
from srx.core.record import decode_structural_payload, parse_record
from srx.core.varint import sha256, sha256_hex


class SRXReconstructor:
    """Exact reconstructor for SRX snapshots, delta patches, and structural records."""

    @staticmethod
    def reconstruct(ref: bytes | None, record: bytes) -> bytes:
        """Reconstruct target artifact from reference bytes and SRX record bytes.
        
        Guarantees exact length and SHA-256 target verification before returning.
        """
        parsed = parse_record(record)
        rh = parsed["ref_hash"]
        th = parsed["target_hash"]
        ts = parsed["target_size"]
        rt = parsed["record_type"]
        payload = parsed["payload"]

        # Validate reference hash if reference is provided
        if ref is not None:
            actual_rh = sha256(ref)
            if actual_rh != rh and rh != b"\x00" * 32:
                raise ValueError(
                    f"Reference hash mismatch: expected {rh.hex()}, got {actual_rh.hex()}"
                )

        if rt == REC_SNAPSHOT:
            out = unzstd(payload)
        elif rt == REC_ZSTD_PATCH:
            if ref is None:
                raise ValueError("Reference bytes required to reconstruct patch record")
            out = unzpatch(ref, payload)
        elif rt == REC_BSDIFF:
            if ref is None:
                raise ValueError("Reference bytes required to reconstruct bsdiff record")
            out = bspatch(ref, payload)
        elif rt == REC_STRUCT:
            if ref is None:
                raise ValueError("Reference bytes required to reconstruct structural record")
            tb, res_type, res = decode_structural_payload(payload)
            ref_obj = JSONAdapter.parse(ref)
            ops = decode_transform(tb, ref_obj)
            pred_obj = apply_ops(ref_obj, ops)
            pred = JSONAdapter.serialize(pred_obj, pretty=True)
            
            if res_type == RES_NONE:
                out = pred
            elif res_type == RES_FORMAT_GAPS:
                out = apply_format_gaps(pred, res)
            else:
                out = unzpatch(pred, res)
        else:
            raise ValueError(f"Unknown record type: {rt}")

        # Exact target size and hash verification
        if len(out) != ts:
            raise ValueError(f"Target size mismatch: reconstructed {len(out)} bytes, expected {ts}")
            
        actual_th = sha256(out)
        if actual_th != th:
            raise ValueError(
                f"Target SHA-256 mismatch: reconstructed {actual_th.hex()}, expected {th.hex()}"
            )

        return out
