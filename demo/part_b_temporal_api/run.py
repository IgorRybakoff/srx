#!/usr/bin/env python3
"""Reproducible SRX Temporal/Evidence demo using the real production core."""

from __future__ import annotations

import tempfile
from pathlib import Path

from srx_temporal.cas import ContentAddressableStore
from srx_temporal.connectors.local_folder import LocalFolderConnector
from srx_temporal.core_adapter import make_production_core
from srx_temporal.ingest import ingest_snapshot
from srx_temporal.reconstructor import SelectiveReconstructor
from srx_temporal.temporal_index import TemporalIndex


def main() -> None:
    here = Path(__file__).resolve().parent
    snapshots = here / "snapshots"

    with tempfile.TemporaryDirectory() as td:
        cas = ContentAddressableStore(Path(td) / "cas")
        index = TemporalIndex(cas)
        connector = LocalFolderConnector()
        core = make_production_core()
        reconstructor = SelectiveReconstructor(index, cas, core)

        timestamps = {
            "v1": "2026-01-01T00:00:00+00:00",
            "v2": "2026-01-02T00:00:00+00:00",
            "v3": "2026-01-03T00:00:00+00:00",
            "v4": "2026-01-04T00:00:00+00:00",
        }

        parent: tuple[str, ...] = ()
        for version_id in ("v1", "v2", "v3", "v4"):
            connector.register_snapshot(
                version_id,
                snapshots / version_id,
                timestamp=timestamps[version_id],
            )
            ingest_snapshot(
                index,
                cas,
                connector,
                version_id,
                parent_ids=parent,
                core=core,
            )
            parent = (version_id,)

        print("=== SRX Temporal / Evidence demo ===")
        print()
        print("--- timeline: database.pool_size ---")
        hits = index.timeline_by_key("database.pool_size", file_path="config.json")
        for hit in hits:
            ev = hit.evidence
            print(
                f"{hit.version_id}: {hit.change_type} "
                f"{ev.previous_value_ref} -> {ev.current_value_ref} "
                f"verified={ev.verification_passed}"
            )

        print()
        print("--- selective reconstruction: v3/config.json ---")
        restored = reconstructor.reconstruct_file("v3", "config.json")
        expected = (snapshots / "v3" / "config.json").read_bytes()
        print(f"bytes={len(restored.bytes_data)}")
        print(f"sha256={restored.sha256}")
        print(f"verification_passed={restored.verification_passed}")
        print(f"byte_equal_to_original={restored.bytes_data == expected}")

        print()
        print("--- reconstructed key: database.driver ---")
        print(reconstructor.reconstruct_key("v3", "config.json", "database.driver"))


if __name__ == "__main__":
    main()
