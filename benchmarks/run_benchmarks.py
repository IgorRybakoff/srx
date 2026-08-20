"""Benchmark suite for SRX Public v0.1 against DevInit and Vite corpora."""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

from srx.adapters.json_adapter import JSONAdapter
from srx.core.compression import zpatch, zstd
from srx.core.constants import REC_STRUCT
from srx.core.evaluate import evaluate_structural
from srx.core.record import create_record, encode_structural_payload
from srx.core.varint import sha256_hex
from srx.reconstruct.reconstructor import SRXReconstructor


ROOT = Path(__file__).resolve().parent.parent


def run_corpus_benchmark(corpus_name: str, file_paths: list[Path]) -> dict[str, Any]:
    """Run full benchmark on an ordered sequence of structured files."""
    files = [p.read_bytes() for p in file_paths]
    version_names = [p.stem for p in file_paths]
    
    first_snapshot_bytes = len(zstd(files[0])) + 82
    conv_cumulative = first_snapshot_bytes
    struct_cumulative = first_snapshot_bytes
    srx_adaptive_cumulative = first_snapshot_bytes
    
    rows: list[dict[str, Any]] = []
    
    for i in range(len(files) - 1):
        v_from = version_names[i]
        v_to = version_names[i + 1]
        ref = files[i]
        tgt = files[i + 1]
        
        # Conventional fallback: snapshot vs patch
        snap_bytes = len(zstd(tgt)) + 82
        patch_bytes = len(zpatch(ref, tgt)) + 82
        conv_bytes = min(snap_bytes, patch_bytes)
        
        best, _ = evaluate_structural(ref, tgt)
        
        # Package and verify exact structural record
        inner = encode_structural_payload(
            best["transform_blob"],
            best["residual_type"],
            best["residual_blob"],
        )
        record = create_record(ref, tgt, REC_STRUCT, inner)
        
        # Exact restoration gate
        reconstructed = SRXReconstructor.reconstruct(ref, record)
        assert reconstructed == tgt
        assert sha256_hex(reconstructed) == sha256_hex(tgt)
        
        struct_bytes = len(record)
        selected = "STRUCTURAL" if struct_bytes < conv_bytes else "CONVENTIONAL"
        adaptive_bytes = min(conv_bytes, struct_bytes)
        
        conv_cumulative += conv_bytes
        struct_cumulative += struct_bytes
        srx_adaptive_cumulative += adaptive_bytes
        
        rows.append({
            "from": v_from,
            "to": v_to,
            "conventional_bytes": conv_bytes,
            "structural_bytes": struct_bytes,
            "selected_strategy": selected,
            "string_delta_ops": best["string_delta_ops"],
            "residual_kind": best["residual_kind"],
            "residual_bytes": best["residual_bytes"],
            "target_sha256": sha256_hex(tgt),
            "exact_restore_verified": True,
        })
        
    gain_pct = 100.0 * (conv_cumulative - srx_adaptive_cumulative) / conv_cumulative
    trans_conv = conv_cumulative - first_snapshot_bytes
    trans_srx = srx_adaptive_cumulative - first_snapshot_bytes
    trans_gain_pct = 100.0 * (trans_conv - trans_srx) / trans_conv if trans_conv > 0 else 0.0
    
    return {
        "corpus": corpus_name,
        "versions_count": len(files),
        "transitions_count": len(rows),
        "first_snapshot_bytes": first_snapshot_bytes,
        "conventional_cumulative_bytes": conv_cumulative,
        "structural_only_cumulative_bytes": struct_cumulative,
        "srx_adaptive_cumulative_bytes": srx_adaptive_cumulative,
        "total_gain_percent": round(gain_pct, 2),
        "transition_gain_percent": round(trans_gain_pct, 2),
        "structural_selected_count": sum(r["selected_strategy"] == "STRUCTURAL" for r in rows),
        "all_exact_restore_verified": True,
        "transitions": rows,
    }


def main() -> dict[str, Any]:
    devinit_dir = ROOT / "benchmarks" / "corpora" / "devinit"
    devinit_files = sorted(devinit_dir.glob("devinit.schema-*.json"))
    
    vite_dir = ROOT / "benchmarks" / "corpora" / "vite"
    vite_files = sorted(vite_dir.glob("v*.json"))
    
    results = {
        "engine": "SRX Public v0.1 Core",
        "devinit": run_corpus_benchmark("devinit", devinit_files),
        "vite": run_corpus_benchmark("vite", vite_files),
    }
    
    out_dir = ROOT / "benchmarks" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "benchmark_report.json").write_text(json.dumps(results, indent=2))
    
    print(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    main()
