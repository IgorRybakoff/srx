from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from srx_temporal.cas import ContentAddressableStore
from srx_temporal.connectors.local_folder import LocalFolderConnector
from srx_temporal.core_adapter import make_production_core
from srx_temporal.evidence import EvidenceResolver
from srx_temporal.errors import CorruptRepresentation, InvalidEvidence
from srx_temporal.ingest import ingest_snapshot
from srx_temporal.models import Evidence
from srx_temporal.reconstructor import SelectiveReconstructor
from srx_temporal.temporal_index import TemporalIndex


class ProductGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cas = ContentAddressableStore(self.tmp / "cas")
        self.index = TemporalIndex(self.cas)
        self.connector = LocalFolderConnector()
        self.core = make_production_core()
        self.recon = SelectiveReconstructor(self.index, self.cas, self.core)
        self.resolver = EvidenceResolver(self.index, self.recon)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _snapshot(self, version: str, obj: dict, timestamp: str):
        root = self.tmp / version
        root.mkdir()
        (root / "config.json").write_text(json.dumps(obj, indent=2) + "\n")
        self.connector.register_snapshot(version, root, timestamp=timestamp)

    def test_nested_json_key_timeline_and_reconstruct_key(self):
        self._snapshot(
            "v1",
            {"database": {"driver": "sqlite", "pool_size": 4}, "app": {"name": "svc"}},
            "2026-08-20T10:00:00+00:00",
        )
        self._snapshot(
            "v2",
            {"database": {"driver": "sqlite", "pool_size": 16}, "app": {"name": "svc"}},
            "2026-08-20T11:00:00+00:00",
        )
        ingest_snapshot(self.index, self.cas, self.connector, "v1", core=self.core)
        ingest_snapshot(self.index, self.cas, self.connector, "v2", parent_ids=("v1",), core=self.core)

        hits = self.index.timeline_by_key("database.pool_size", file_path="config.json")
        self.assertEqual([h.version_id for h in hits], ["v1", "v2"])
        self.assertEqual([h.change_type for h in hits], ["key_added", "value_changed"])
        self.assertTrue(all(h.evidence.verification_passed for h in hits))
        self.assertEqual(self.recon.reconstruct_key("v2", "config.json", "database.pool_size"), 16)

    def test_evidence_is_real_reconstruction_not_cas_presence(self):
        self._snapshot("v1", {"budget": {"total": 100}}, "2026-08-20T10:00:00+00:00")
        ingest_snapshot(self.index, self.cas, self.connector, "v1", core=self.core)

        hits = self.index.timeline_by_key("budget.total", file_path="config.json")
        self.assertEqual(len(hits), 1)
        self.assertTrue(hits[0].evidence.verification_passed)

        entry = self.index.get_manifest("v1").files[0]
        ref_path = self.cas._path_for(entry.representation_ref.split(":", 1)[1])
        ref_path.write_bytes(b"present-but-corrupt")

        with self.assertRaises(CorruptRepresentation):
            self.index.timeline_by_key("budget.total", file_path="config.json")

    def test_invalid_evidence_hash_is_blocked(self):
        self._snapshot("v1", {"x": 1}, "2026-08-20T10:00:00+00:00")
        ingest_snapshot(self.index, self.cas, self.connector, "v1", core=self.core)
        good = self.index.timeline_by_key("x", file_path="config.json")[0].evidence
        bad = Evidence(
            version_id=good.version_id,
            timestamp=good.timestamp,
            file_path=good.file_path,
            key_path=good.key_path,
            source_sha256="0" * 64,
            reconstructed_path=None,
            verification_passed=False,
            change_type=good.change_type,
            previous_value_ref=good.previous_value_ref,
            current_value_ref=good.current_value_ref,
        )
        with self.assertRaises(InvalidEvidence):
            self.resolver.resolve(bad)


    def test_backdated_child_does_not_invert_causal_timeline(self):
        self._snapshot("v1", {"x": 1}, "2026-08-20T11:00:00+00:00")
        self._snapshot("v2", {"x": 2}, "2026-08-20T10:00:00+00:00")
        ingest_snapshot(self.index, self.cas, self.connector, "v1", core=self.core)
        ingest_snapshot(self.index, self.cas, self.connector, "v2", parent_ids=("v1",), core=self.core)

        versions = self.index.list_versions()
        self.assertEqual([m.version_id for m in versions], ["v1", "v2"])
        hits = self.index.timeline_by_key("x", file_path="config.json")
        self.assertEqual([h.version_id for h in hits], ["v1", "v2"])

    def test_deleted_file_evidence_resolves_to_parent_exact_source(self):
        root1 = self.tmp / "d1"
        root1.mkdir()
        (root1 / "budget.json").write_text(json.dumps({"total": 100}) + "\n")
        self.connector.register_snapshot("d1", root1, timestamp="2026-08-20T10:00:00+00:00")
        ingest_snapshot(self.index, self.cas, self.connector, "d1", core=self.core)

        root2 = self.tmp / "d2"
        root2.mkdir()
        self.connector.register_snapshot("d2", root2, timestamp="2026-08-20T11:00:00+00:00")
        ingest_snapshot(self.index, self.cas, self.connector, "d2", parent_ids=("d1",), core=self.core)

        hits = self.index.timeline_by_file("budget.json")
        self.assertEqual([h.change_type for h in hits], ["added", "deleted"])
        self.assertTrue(all(h.evidence.verification_passed for h in hits))
        self.assertEqual(hits[-1].evidence.source_sha256, hits[0].evidence.source_sha256)


if __name__ == "__main__":
    unittest.main()
