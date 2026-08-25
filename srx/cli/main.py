"""SRX Command Line Interface (CLI).

Commands:
- srx diff <v1> <v2> [--structural] [--json] [-o <output-record>]
- srx reconstruct <record-file> [--ref <ref-file>] -o <output-file>
- srx verify <record-file> [--ref <ref-file>]
- srx stats <record-file>
- srx temporal <init|add|list|timeline|reconstruct|evidence> ...
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

from srx.adapters.json_adapter import JSONAdapter
from srx.core.constants import (
    REC_BSDIFF,
    REC_SNAPSHOT,
    REC_STRUCT,
    REC_ZSTD_PATCH,
    RES_FORMAT_GAPS,
    RES_NONE,
    RES_PATCH,
)
from srx.core.evaluate import evaluate_structural
from srx.core.record import (
    create_record,
    decode_structural_payload,
    encode_structural_payload,
    parse_record,
)
from srx.core.varint import sha256_hex
from srx.reconstruct.reconstructor import SRXReconstructor
from srx.reconstruct.verifier import SRXVerifier

RECORD_TYPE_NAMES = {
    REC_SNAPSHOT: "SNAPSHOT",
    REC_ZSTD_PATCH: "ZSTD_PATCH",
    REC_BSDIFF: "BSDIFF",
    REC_STRUCT: "STRUCTURAL",
}

RESIDUAL_TYPE_NAMES = {
    RES_NONE: "NONE",
    RES_FORMAT_GAPS: "FORMAT_GAPS",
    RES_PATCH: "PATCH",
}


def cmd_diff(args: argparse.Namespace) -> int:
    """Compare two structured files and compute structural transformation and record."""
    v1_path = Path(args.v1)
    v2_path = Path(args.v2)

    if not v1_path.exists():
        print(f"Error: Reference file '{v1_path}' does not exist", file=sys.stderr)
        return 1
    if not v2_path.exists():
        print(f"Error: Target file '{v2_path}' does not exist", file=sys.stderr)
        return 1

    ref_bytes = v1_path.read_bytes()
    tgt_bytes = v2_path.read_bytes()

    best, all_cands = evaluate_structural(ref_bytes, tgt_bytes)

    # Encode structural record container
    inner_payload = encode_structural_payload(
        best["transform_blob"],
        best["residual_type"],
        best["residual_blob"],
    )
    record_bytes = create_record(ref_bytes, tgt_bytes, REC_STRUCT, inner_payload)

    if args.output:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(record_bytes)

    # Verify round-trip immediately
    reconstructed = SRXReconstructor.reconstruct(ref_bytes, record_bytes)
    assert reconstructed == tgt_bytes

    if args.json:
        out_obj = {
            "reference_file": str(v1_path),
            "target_file": str(v2_path),
            "reference_size": len(ref_bytes),
            "target_size": len(tgt_bytes),
            "reference_sha256": sha256_hex(ref_bytes),
            "target_sha256": sha256_hex(tgt_bytes),
            "structural_record_bytes": len(record_bytes),
            "logical_candidate": best["logical_candidate"],
            "physical_encoding": best["encoding"],
            "operation_count": best["op_count"],
            "string_delta_ops": best["string_delta_ops"],
            "residual_kind": best["residual_kind"],
            "residual_bytes": best["residual_bytes"],
            "verified_exact": True,
            "saved_record_to": str(args.output) if args.output else None,
            "candidates_evaluated": len(all_cands),
        }
        print(json.dumps(out_obj, indent=2))
        return 0

    print("=" * 60)
    print("SRX Structural Diff & Transformation Result")
    print("=" * 60)
    print(f"Reference : {v1_path} ({len(ref_bytes):,} bytes | {sha256_hex(ref_bytes)[:16]}...)")
    print(f"Target    : {v2_path} ({len(tgt_bytes):,} bytes | {sha256_hex(tgt_bytes)[:16]}...)")
    print("-" * 60)
    print(f"Logical Candidate   : {best['logical_candidate']}")
    print(f"Encoding            : {best['encoding']}")
    print(f"Operations Count    : {best['op_count']}")
    print(f"String Delta Ops    : {best['string_delta_ops']}")
    print(f"Residual Kind       : {best['residual_kind']} ({best['residual_bytes']} bytes)")
    print(f"Transform Bytes     : {best['transform_bytes']} bytes (raw: {best['raw_transform_bytes']} bytes)")
    print(f"Total Record Size   : {len(record_bytes)} bytes")
    print(f"Exact Verification  : PASS (SHA-256 matched)")
    if args.output:
        print(f"Output Record File  : {args.output}")
    print("=" * 60)
    return 0


def cmd_reconstruct(args: argparse.Namespace) -> int:
    """Reconstruct target artifact from SRX record container."""
    rec_path = Path(args.record)
    if not rec_path.exists():
        print(f"Error: Record file '{rec_path}' does not exist", file=sys.stderr)
        return 1

    ref_bytes = None
    if args.ref:
        ref_path = Path(args.ref)
        if not ref_path.exists():
            print(f"Error: Reference file '{ref_path}' does not exist", file=sys.stderr)
            return 1
        ref_bytes = ref_path.read_bytes()

    record_bytes = rec_path.read_bytes()

    try:
        reconstructed = SRXReconstructor.reconstruct(ref_bytes, record_bytes)
    except Exception as e:
        print(f"Reconstruction failed: {e}", file=sys.stderr)
        return 1

    out_p = Path(args.output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_bytes(reconstructed)

    if args.json:
        res = {
            "status": "SUCCESS",
            "record_file": str(rec_path),
            "output_file": str(out_p),
            "reconstructed_bytes": len(reconstructed),
            "sha256": sha256_hex(reconstructed),
            "verified": True,
        }
        print(json.dumps(res, indent=2))
        return 0

    print(f"Successfully reconstructed {len(reconstructed):,} bytes -> {out_p}")
    print(f"Target SHA-256: {sha256_hex(reconstructed)}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Cryptographically verify an SRX record."""
    rec_path = Path(args.record)
    if not rec_path.exists():
        print(f"Error: Record file '{rec_path}' does not exist", file=sys.stderr)
        return 1

    ref_bytes = None
    if args.ref:
        ref_path = Path(args.ref)
        if not ref_path.exists():
            print(f"Error: Reference file '{ref_path}' does not exist", file=sys.stderr)
            return 1
        ref_bytes = ref_path.read_bytes()

    record_bytes = rec_path.read_bytes()
    evidence = SRXVerifier.verify_record(ref_bytes, record_bytes)

    if args.json:
        # Exclude raw byte payload for clean JSON output
        out_ev = {k: v for k, v in evidence.items() if k != "reconstructed_bytes"}
        out_ev["record_file"] = str(rec_path)
        print(json.dumps(out_ev, indent=2))
        return 0 if evidence["verified"] else 1

    print("=" * 60)
    print("SRX Exact Reconstruction Verification Report")
    print("=" * 60)
    print(f"Record File     : {rec_path}")
    print(f"Record Type     : {evidence['record_type']}")
    print(f"Record Size     : {evidence['record_bytes']:,} bytes")
    print(f"Expected Target : {evidence['expected_target_hash']}")
    print(f"Actual Target   : {evidence['actual_target_hash']}")
    print(f"Reference Hash  : {evidence['reference_hash']}")
    print(f"Target Size     : {evidence['target_size_bytes']:,} bytes")
    print("-" * 60)
    if evidence["verified"]:
        print("VERIFICATION RESULT: [ PASS ] Exact match verified.")
        print("=" * 60)
        return 0
    else:
        print(f"VERIFICATION RESULT: [ FAIL ] {evidence['error']}")
        print("=" * 60)
        return 1


def cmd_stats(args: argparse.Namespace) -> int:
    """Inspect and display container header stats for an SRX record."""
    rec_path = Path(args.record)
    if not rec_path.exists():
        print(f"Error: Record file '{rec_path}' does not exist", file=sys.stderr)
        return 1

    record_bytes = rec_path.read_bytes()
    try:
        parsed = parse_record(record_bytes)
    except Exception as e:
        print(f"Error parsing record: {e}", file=sys.stderr)
        return 1

    rt_name = RECORD_TYPE_NAMES.get(parsed["record_type"], "UNKNOWN")

    info: dict = {
        "file": str(rec_path),
        "total_record_bytes": len(record_bytes),
        "magic": parsed["magic"].decode("ascii", errors="replace"),
        "record_type": rt_name,
        "ref_hash_hex": parsed["ref_hash"].hex(),
        "target_hash_hex": parsed["target_hash"].hex(),
        "target_uncompressed_size": parsed["target_size"],
        "payload_bytes": parsed["payload_len"],
    }

    if parsed["record_type"] == REC_STRUCT:
        try:
            tb, res_type, res = decode_structural_payload(parsed["payload"])
            enc_name = {1: "RAW_OPS", 2: "ZSTD_OPS", 3: "CTX_PATHS"}.get(tb[0] if tb else 0, "UNKNOWN")
            info["structural_details"] = {
                "transform_bytes": len(tb),
                "transform_encoding": enc_name,
                "residual_type": RESIDUAL_TYPE_NAMES.get(res_type, f"TYPE_{res_type}"),
                "residual_bytes": len(res),
            }
        except Exception:
            pass

    if args.json:
        print(json.dumps(info, indent=2))
        return 0

    print("=" * 60)
    print("SRX Record Container Statistics")
    print("=" * 60)
    print(f"File                  : {info['file']}")
    print(f"Total Record Size     : {info['total_record_bytes']:,} bytes")
    print(f"Record Type           : {info['record_type']}")
    print(f"Reference SHA-256     : {info['ref_hash_hex']}")
    print(f"Target SHA-256        : {info['target_hash_hex']}")
    print(f"Target Uncompressed   : {info['target_uncompressed_size']:,} bytes")
    print(f"Payload Size          : {info['payload_bytes']:,} bytes")
    if "structural_details" in info:
        sd = info["structural_details"]
        print("-" * 60)
        print("Structural Payload Breakdown:")
        print(f"  Transform Bytes     : {sd['transform_bytes']} bytes ({sd['transform_encoding']})")
        print(f"  Residual Type       : {sd['residual_type']} ({sd['residual_bytes']} bytes)")
    print("=" * 60)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build SRX command line parser."""
    parser = argparse.ArgumentParser(
        prog="srx",
        description="SRX Public v0.1: Exact reconstructive engine for evolving structured data.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # diff command
    diff_p = subparsers.add_parser("diff", help="Compute structural diff and record between two versions")
    diff_p.add_argument("v1", help="Path to reference version file (v1)")
    diff_p.add_argument("v2", help="Path to target version file (v2)")
    diff_p.add_argument("--structural", action="store_true", default=True, help="Use structural engine (default)")
    diff_p.add_argument("--file", action="store_true", help="File level diff flag")
    diff_p.add_argument("-o", "--output", help="Save output SRX record to path")
    diff_p.add_argument("--json", action="store_true", help="Output results in JSON format")

    # reconstruct command
    rec_p = subparsers.add_parser("reconstruct", help="Reconstruct target from an SRX record")
    rec_p.add_argument("record", help="Path to SRX record file")
    rec_p.add_argument("--ref", help="Path to reference version file")
    rec_p.add_argument("-o", "--output", required=True, help="Path to save reconstructed artifact")
    rec_p.add_argument("--file", action="store_true", help="File level reconstruction flag")
    rec_p.add_argument("--json", action="store_true", help="Output results in JSON format")

    # verify command
    ver_p = subparsers.add_parser("verify", help="Verify exact reconstruction and SHA-256 of an SRX record")
    ver_p.add_argument("record", help="Path to SRX record file")
    ver_p.add_argument("--ref", help="Path to reference version file")
    ver_p.add_argument("--json", action="store_true", help="Output results in JSON format")

    # stats command
    stat_p = subparsers.add_parser("stats", help="Show metadata and byte composition of an SRX record")
    stat_p.add_argument("record", help="Path to SRX record file")
    stat_p.add_argument("--json", action="store_true", help="Output results in JSON format")

    # temporal namespace
    temporal_p = subparsers.add_parser(
        "temporal", help="Persistent temporal/evidence queries and reconstruction"
    )
    temporal_sub = temporal_p.add_subparsers(
        dest="temporal_command", required=True, help="Temporal commands"
    )

    temporal_init = temporal_sub.add_parser("init", help="Initialize a temporal store")
    temporal_init.add_argument("store")
    temporal_init.add_argument(
        "--force", action="store_true", help="Reinitialize store and remove its old CAS"
    )

    temporal_add = temporal_sub.add_parser("add", help="Add a snapshot as a new version")
    temporal_add.add_argument("store")
    temporal_add.add_argument("snapshot")
    temporal_add.add_argument("-m", "--message", required=True)

    temporal_list = temporal_sub.add_parser("list", help="List committed versions")
    temporal_list.add_argument("store")

    temporal_timeline = temporal_sub.add_parser("timeline", help="Query nested key history")
    temporal_timeline.add_argument("store")
    temporal_timeline.add_argument("--key", required=True)
    temporal_timeline.add_argument("--file", default=None)
    temporal_timeline.add_argument(
        "--json", action="store_true", help="Output verified timeline as JSON"
    )

    temporal_reconstruct = temporal_sub.add_parser(
        "reconstruct", help="Selectively reconstruct one historical file"
    )
    temporal_reconstruct.add_argument("store")
    temporal_reconstruct.add_argument("version")
    temporal_reconstruct.add_argument("--file", required=True)
    temporal_reconstruct.add_argument("-o", "--output", required=True)

    temporal_evidence = temporal_sub.add_parser(
        "evidence", help="Resolve verified evidence for a nested key"
    )
    temporal_evidence.add_argument("store")
    temporal_evidence.add_argument("--key", required=True)
    temporal_evidence.add_argument("--file", default=None)
    temporal_evidence.add_argument(
        "--json", action="store_true", help="Output verified evidence as JSON"
    )

    return parser


def cli_entry(args: list[str] | None = None) -> int:
    """Main CLI entrypoint function."""
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    if not parsed_args.command:
        parser.print_help()
        return 0

    if parsed_args.command == "diff":
        return cmd_diff(parsed_args)
    elif parsed_args.command == "reconstruct":
        return cmd_reconstruct(parsed_args)
    elif parsed_args.command == "verify":
        return cmd_verify(parsed_args)
    elif parsed_args.command == "stats":
        return cmd_stats(parsed_args)
    elif parsed_args.command == "temporal":
        from srx.cli.temporal import dispatch_temporal

        return dispatch_temporal(parsed_args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(cli_entry())
