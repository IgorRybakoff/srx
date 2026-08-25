"""Persistent temporal/evidence CLI for SRX.

The commands in this module expose the existing ``srx_temporal`` engine. They
never replace reconstruction, evidence verification, CAS semantics, or core
representation selection with a second simplified implementation.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from srx_temporal.cas import ContentAddressableStore
from srx_temporal.connectors.local_folder import LocalFolderConnector
from srx_temporal.core_adapter import make_production_core
from srx_temporal.ingest import ingest_snapshot
from srx_temporal.persistence import MANIFEST_FILENAME, load_index, save_index
from srx_temporal.reconstructor import SelectiveReconstructor
from srx_temporal.temporal_index import TemporalIndex


def _manifest_path(store_path: Path) -> Path:
    return Path(store_path) / MANIFEST_FILENAME


def _load_required(store_path: Path) -> TemporalIndex:
    store_path = Path(store_path)
    manifest_path = _manifest_path(store_path)
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"store {store_path} is not initialized; run 'srx temporal init {store_path}' first"
        )
    return load_index(store_path)


def _print_error(exc: Exception) -> int:
    print(f"Error: {exc}", file=sys.stderr)
    return 1


def _next_version_id(index: TemporalIndex) -> str:
    used = {manifest.version_id for manifest in index.list_versions()}
    number = 1
    while f"v{number}" in used:
        number += 1
    return f"v{number}"


def cmd_temporal_init(args: argparse.Namespace) -> int:
    store_path = Path(args.store)
    manifest_path = _manifest_path(store_path)

    if manifest_path.exists() and not args.force:
        return _print_error(
            ValueError(
                f"store {store_path} already exists; use --force to reinitialize it"
            )
        )

    if args.force:
        cas_path = store_path / "cas"
        if cas_path.exists():
            shutil.rmtree(cas_path)
        if manifest_path.exists():
            manifest_path.unlink()

    try:
        store_path.mkdir(parents=True, exist_ok=True)
        cas = ContentAddressableStore(store_path / "cas")
        index = TemporalIndex(cas)
        save_index(index, store_path)
    except (OSError, ValueError) as exc:
        return _print_error(exc)

    print(f"Initialized SRX temporal store at {store_path}")
    return 0


def cmd_temporal_add(args: argparse.Namespace) -> int:
    store_path = Path(args.store)
    snapshot_path = Path(args.snapshot)
    if not snapshot_path.is_dir():
        return _print_error(
            ValueError(f"snapshot directory does not exist: {snapshot_path}")
        )

    try:
        index = _load_required(store_path)
        core = make_production_core()
        existing = index.list_versions()
        version_id = _next_version_id(index)
        parent_ids = (existing[-1].version_id,) if existing else ()

        connector = LocalFolderConnector()
        connector.register_snapshot(version_id, snapshot_path)
        ingest_snapshot(
            index=index,
            cas=index.cas,
            connector=connector,
            version_id=version_id,
            parent_ids=parent_ids,
            message=args.message,
            core=core,
        )
        save_index(index, store_path)
    except Exception as exc:  # CLI boundary: surface failures, never hide them.
        return _print_error(exc)

    print(f"Added version {version_id}")
    return 0


def cmd_temporal_list(args: argparse.Namespace) -> int:
    try:
        index = _load_required(Path(args.store))
    except (OSError, ValueError) as exc:
        return _print_error(exc)

    versions = index.list_versions()
    if not versions:
        print("No versions in store.")
        return 0

    print(f"Versions in {args.store}:")
    for manifest in versions:
        parents = ",".join(manifest.parent_ids) if manifest.parent_ids else "-"
        message = manifest.message or ""
        print(
            f"  {manifest.version_id}  parents={parents}  "
            f"{manifest.timestamp}  {message}"
        )
    return 0


def _verified_key_hits(args: argparse.Namespace):
    index = _load_required(Path(args.store))
    core = make_production_core()
    # Construction binds EvidenceResolver into the index. Every hit returned
    # below is therefore re-resolved through exact reconstruction + SHA-256.
    SelectiveReconstructor(index, index.cas, core)
    return index.timeline_by_key(args.key, file_path=args.file)


def cmd_temporal_timeline(args: argparse.Namespace) -> int:
    try:
        hits = _verified_key_hits(args)
    except Exception as exc:
        return _print_error(exc)

    if not hits:
        print(f"No changes found for key '{args.key}'")
        return 0

    print(f"Timeline for '{args.key}':")
    for hit in hits:
        previous = hit.evidence.previous_value_ref
        current = hit.evidence.current_value_ref
        print(
            f"  {hit.version_id}  {hit.timestamp}  {hit.file_path}  "
            f"{hit.change_type}"
        )
        print(f"    {previous!s} -> {current!s}")
    return 0


def cmd_temporal_reconstruct(args: argparse.Namespace) -> int:
    try:
        index = _load_required(Path(args.store))
        core = make_production_core()
        reconstructor = SelectiveReconstructor(index, index.cas, core)
        result = reconstructor.reconstruct_file(args.version, args.file)

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(result.bytes_data)
    except Exception as exc:
        return _print_error(exc)

    print(f"Reconstructed {len(result.bytes_data)} bytes to {output_path}")
    print(f"SHA-256: {result.sha256}")
    print(f"Verification: {'PASS' if result.verification_passed else 'FAIL'}")
    return 0


def cmd_temporal_evidence(args: argparse.Namespace) -> int:
    try:
        hits = _verified_key_hits(args)
    except Exception as exc:
        return _print_error(exc)

    if not hits:
        print(f"No evidence found for key '{args.key}'")
        return 0

    print(f"Evidence for '{args.key}':")
    for hit in hits:
        evidence = hit.evidence
        print(f"  Version: {evidence.version_id}")
        print(f"  File: {evidence.file_path}")
        print(f"  Change: {evidence.change_type}")
        print(f"  Source SHA-256: {evidence.source_sha256}")
        print(
            "  Verification: "
            f"{'PASS' if evidence.verification_passed else 'FAIL'}"
        )
        print(f"  Previous ref: {evidence.previous_value_ref}")
        print(f"  Current ref: {evidence.current_value_ref}")
    return 0


def dispatch_temporal(args: argparse.Namespace) -> int:
    handlers = {
        "init": cmd_temporal_init,
        "add": cmd_temporal_add,
        "list": cmd_temporal_list,
        "timeline": cmd_temporal_timeline,
        "reconstruct": cmd_temporal_reconstruct,
        "evidence": cmd_temporal_evidence,
    }
    handler = handlers.get(args.temporal_command)
    if handler is None:
        return _print_error(ValueError("missing temporal command"))
    return handler(args)
