"""Selectively reconstruct one historical file using the production SRX core."""

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
        reconstructor = SelectiveReconstructor(index, cas, core)

        root = tmp / "snapshot"
        root.mkdir()
        (root / "deployment.json").write_text(json.dumps({"replicas": 1}))
        (root / "service.json").write_text(json.dumps({"port": 8080}))
        (root / "policy.json").write_text(json.dumps({"retries": 3}))

        connector.register_snapshot("v0", root, timestamp="2026-01-01T00:00:00+00:00")
        ingest_snapshot(index, cas, connector, "v0", core=core)

        result = reconstructor.reconstruct_file("v0", "deployment.json")
        print(f"file={result.file_path}")
        print(f"version={result.version_id}")
        print(f"sha256={result.sha256}")
        print(f"verification_passed={result.verification_passed}")
        print(f"content={result.bytes_data.decode()}")
        print(f"replicas={reconstructor.reconstruct_key('v0', 'deployment.json', 'replicas')}")


if __name__ == "__main__":
    main()
