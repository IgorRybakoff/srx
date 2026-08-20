from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from srx.core.record import parse_record
from srx.public_api import SRXCoreAPI
from srx_temporal.cas import ContentAddressableStore
from srx_temporal.connectors.local_folder import LocalFolderConnector
from srx_temporal.core_adapter import make_production_core
from srx_temporal.ingest import ingest_snapshot
from srx_temporal.reconstructor import SelectiveReconstructor
from srx_temporal.temporal_index import TemporalIndex


class RealCoreIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cas = ContentAddressableStore(self.tmp / "cas")
        self.index = TemporalIndex(self.cas)
        self.connector = LocalFolderConnector()
        self.core = make_production_core()
        self.recon = SelectiveReconstructor(self.index, self.cas, self.core)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _snapshot(self, name: str, obj: dict, ts: str) -> Path:
        root = self.tmp / name
        root.mkdir()
        (root / "config.json").write_text(json.dumps(obj, indent=2) + "\n")
        self.connector.register_snapshot(name, root, timestamp=ts)
        return root

    def test_real_core_records_roundtrip_across_versions(self):
        self._snapshot("v1", {"pool_size": 4, "driver": "sqlite"}, "2026-08-20T10:00:00+00:00")
        self._snapshot("v2", {"pool_size": 16, "driver": "sqlite"}, "2026-08-20T11:00:00+00:00")
        self._snapshot("v3", {"pool_size": 16, "driver": "postgres"}, "2026-08-20T12:00:00+00:00")

        ingest_snapshot(self.index, self.cas, self.connector, "v1", core=self.core)
        ingest_snapshot(self.index, self.cas, self.connector, "v2", parent_ids=("v1",), core=self.core)
        ingest_snapshot(self.index, self.cas, self.connector, "v3", parent_ids=("v2",), core=self.core)

        for version in ("v1", "v2", "v3"):
            entry = self.index.get_manifest(version).files[0]
            representation = self.cas.get(entry.representation_ref)
            self.assertEqual(representation[:5], b"SRXH1")
            parse_record(representation)  # must be a real SRX record
            restored = self.recon.reconstruct_file(version, "config.json")
            self.assertTrue(restored.verification_passed)
            expected = self.connector.read_file(version, "config.json")
            self.assertEqual(restored.bytes_data, expected)

        hits = self.index.timeline_by_key("pool_size", file_path="config.json")
        self.assertEqual([h.version_id for h in hits], ["v1", "v2"])

    def test_public_encoder_output_is_consumable_by_public_reconstructor(self):
        ref = b'{"value":1}\n'
        target = b'{"value":2}\n'
        record = SRXCoreAPI.encode(ref, target)
        out = SRXCoreAPI.reconstruct(ref if SRXCoreAPI.requires_reference(record) else None, record)
        self.assertEqual(out, target)


if __name__ == "__main__":
    unittest.main()
