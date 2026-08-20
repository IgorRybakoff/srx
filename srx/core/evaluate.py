"""Adaptive cost selector and structural candidate evaluation."""

import json
from typing import Any
from srx.core.codec import decode_transform, encode_transform_candidates
from srx.core.compression import unzpatch, zpatch
from srx.core.constants import (
    RECORD_CONTAINER_HEADER_SIZE,
    RES_FORMAT_GAPS,
    RES_NONE,
    RES_PATCH,
    STRUCTURAL_HEADER_SIZE,
)
from srx.core.diff import diff_json_variants
from srx.core.format_gaps import apply_format_gaps, encode_format_gaps
from srx.core.ops import apply_ops


def _pretty_json(v: Any) -> bytes:
    return (json.dumps(v, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def evaluate_structural(ref: bytes, target: bytes) -> tuple[dict, list[dict]]:
    """Evaluate structural transformation representations and residuals.
    
    Returns (best_candidate, all_evaluated_candidates).
    Guarantees 100% round-trip exact verification of every candidate.
    """
    ro = json.loads(ref)
    to = json.loads(target)
    logical = diff_json_variants(ro, to)
    evaluated: list[dict] = []
    
    for logical_label, ops in logical:
        pred_obj = apply_ops(ro, ops)
        pred = _pretty_json(pred_obj)
        
        if pred == target:
            residual = b""
            residual_kind = "NONE"
            residual_type = RES_NONE
        else:
            zp = zpatch(pred, target)
            fg = encode_format_gaps(pred, target)
            if fg is not None and len(fg) < len(zp):
                residual = fg
                residual_kind = "FORMAT_GAPS"
                residual_type = RES_FORMAT_GAPS
            else:
                residual = zp
                residual_kind = "ZSTD_PATCH"
                residual_type = RES_PATCH
                
        for enc_name, tb, rawlen, modes in encode_transform_candidates(ops, ro):
            # Verify decode and exact restoration
            ops2 = decode_transform(tb, ro)
            pred2 = _pretty_json(apply_ops(ro, ops2))
            
            if residual_kind == "NONE":
                rest = pred2
            elif residual_kind == "FORMAT_GAPS":
                rest = apply_format_gaps(pred2, residual)
            else:
                rest = unzpatch(pred2, residual)
                
            assert rest == target, "Candidate reconstruction failed exact match verification!"
            
            total_bytes = (
                RECORD_CONTAINER_HEADER_SIZE
                + STRUCTURAL_HEADER_SIZE
                + len(tb)
                + len(residual)
            )
            
            evaluated.append({
                "logical_candidate": logical_label,
                "encoding": enc_name,
                "ops": ops,
                "op_count": len(ops),
                "transform_bytes": len(tb),
                "transform_blob": tb,
                "raw_transform_bytes": rawlen,
                "string_delta_ops": sum(x == "STRING_DELTA" for x in modes),
                "residual_kind": residual_kind,
                "residual_type": residual_type,
                "residual_bytes": len(residual),
                "residual_blob": residual,
                "structural_record_bytes": total_bytes,
            })
            
    best = min(evaluated, key=lambda x: x["structural_record_bytes"])
    return best, evaluated
