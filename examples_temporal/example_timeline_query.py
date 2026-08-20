"""Build a small history and query it using the production SRX core."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from srx_temporal.cas import ContentAddressableStore
from srx_temporal.connectors.local_folder import LocalFolderConnector
from srx_temporal.core_adapter import make_production_core
from srx_temporal.ingest import ingest_snapshot
from srx_temporal.reconstructor import SelectiveReconstructor
from srx_temporal.temporal_index import TemporalIndex


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cas = ContentAddressableStore(tmp / "cas")
        index = TemporalIndex(cas)
        connector = LocalFolderConnector()
        core = make_production_core()
        SelectiveReconstructor(index, cas, core)  # binds EvidenceResolver

        states = [
            ("v0", "2026-01-01T00:00:00+00:00", {"replicas": 1, "image": "app:1.0"}),
            ("v1", "2026-02-01T00:00:00+00:00", {"replicas": 3, "image": "app:1.0"}),
            ("v2", "2026-03-01T00:00:00+00:00", {"replicas": 3, "image": "app:1.1"}),
        ]

        parent: tuple[str, ...] = ()
        for version_id, ts, state in states:
            root = tmp / "snapshots" / version_id
            root.mkdir(parents=True)
            (root / "deployment.json").write_text(json.dumps(state))
            connector.register_snapshot(version_id, root, timestamp=ts)
            ingest_snapshot(index, cas, connector, version_id, parent_ids=parent, core=core)
            parent = (version_id,)

        print("=== timeline_by_key('replicas') ===")
        for hit in index.timeline_by_key("replicas", file_path="deployment.json"):
            print(f"{hit.version_id}: {hit.change_type} verified={hit.evidence.verification_passed}")


if __name__ == "__main__":
    main()
