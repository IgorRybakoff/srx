from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from srx.cli.main import cli_entry
from srx_temporal.cas import ContentAddressableStore
from srx_temporal.connectors.local_folder import LocalFolderConnector
from srx_temporal.core_adapter import StubCoreReconstructor
from srx_temporal.ingest import ingest_snapshot
from srx_temporal.persistence import load_index, save_index
from srx_temporal.reconstructor import SelectiveReconstructor
from srx_temporal.temporal_index import TemporalIndex


class TemporalPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _snapshot(self, name: str, pool_size: int, driver: str = "sqlite") -> Path:
        root = self.tmp / "snapshots" / name
        root.mkdir(parents=True, exist_ok=True)
        payload = {
            "app": {"name": "myservice", "version": "1.0.0"},
            "database": {
                "driver": driver,
                "pool_size": pool_size,
                "url": "sqlite:///data.db" if driver == "sqlite" else "postgres://localhost/mydb",
            },
        }
        if name == "v4":
            payload["cache"] = {"driver": "redis", "ttl": 3600}
        (root / "config.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        return root

    def test_persistence_roundtrip_preserves_full_temporal_state(self):
        store = self.tmp / "store"
        cas = ContentAddressableStore(store / "cas")
        index = TemporalIndex(cas)
        connector = LocalFolderConnector()
        core = StubCoreReconstructor()

        snapshots = [
            self._snapshot("v1", 4),
            self._snapshot("v2", 16),
            self._snapshot("v3", 16, "postgres"),
            self._snapshot("v4", 32, "postgres"),
        ]
        for number, root in enumerate(snapshots, start=1):
            version_id = f"v{number}"
            connector.register_snapshot(version_id, root)
            ingest_snapshot(
                index,
                cas,
                connector,
                version_id,
                parent_ids=(f"v{number - 1}",) if number > 1 else (),
                message=f"version {number}",
                core=core,
            )

        committed_before = list(index.iter_committed())
        save_index(index, store)

        del index
        loaded = load_index(store)
        committed_after = list(loaded.iter_committed())
        self.assertEqual(committed_after, committed_before)

        reconstructor = SelectiveReconstructor(loaded, loaded.cas, core)
        result = reconstructor.reconstruct_file("v3", "config.json")
        self.assertTrue(result.verification_passed)
        self.assertEqual(result.bytes_data, (snapshots[2] / "config.json").read_bytes())

        hits = loaded.timeline_by_key("database.pool_size", file_path="config.json")
        self.assertEqual([hit.version_id for hit in hits], ["v1", "v2", "v4"])
        self.assertTrue(all(hit.evidence.verification_passed for hit in hits))

    def test_cli_end_to_end_uses_real_srx_core_after_reload(self):
        store = self.tmp / "cli-store"
        snapshots = [
            self._snapshot("v1", 4),
            self._snapshot("v2", 16),
            self._snapshot("v3", 16, "postgres"),
            self._snapshot("v4", 32, "postgres"),
        ]

        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(cli_entry(["temporal", "init", str(store)]), 0)
            for number, snapshot in enumerate(snapshots, start=1):
                self.assertEqual(
                    cli_entry(
                        [
                            "temporal",
                            "add",
                            str(store),
                            str(snapshot),
                            "-m",
                            f"version {number}",
                        ]
                    ),
                    0,
                )

            self.assertEqual(cli_entry(["temporal", "list", str(store)]), 0)
            self.assertEqual(
                cli_entry(
                    [
                        "temporal",
                        "timeline",
                        str(store),
                        "--key",
                        "database.pool_size",
                        "--file",
                        "config.json",
                    ]
                ),
                0,
            )
            self.assertEqual(
                cli_entry(
                    [
                        "temporal",
                        "evidence",
                        str(store),
                        "--key",
                        "database.pool_size",
                        "--file",
                        "config.json",
                    ]
                ),
                0,
            )

            restored = self.tmp / "restored-v3.json"
            self.assertEqual(
                cli_entry(
                    [
                        "temporal",
                        "reconstruct",
                        str(store),
                        "v3",
                        "--file",
                        "config.json",
                        "-o",
                        str(restored),
                    ]
                ),
                0,
            )

        self.assertEqual(stderr.getvalue(), "")
        output = stdout.getvalue()
        self.assertIn("Timeline for 'database.pool_size'", output)
        self.assertIn("Evidence for 'database.pool_size'", output)
        self.assertIn("Verification: PASS", output)
        self.assertEqual(restored.read_bytes(), (snapshots[2] / "config.json").read_bytes())

        # Reload independently and prove the persistent CAS contains real SRX
        # record containers rather than raw full-file copies.
        loaded = load_index(store)
        for manifest in loaded.list_versions():
            entry = next(item for item in manifest.files if item.path == "config.json")
            representation = loaded.cas.get(entry.representation_ref)
            self.assertEqual(representation[:5], b"SRXH1")

    def test_temporal_json_output_is_machine_readable_and_verified(self):
        store = self.tmp / "json-store"
        snapshots = [
            self._snapshot("v1", 4),
            self._snapshot("v2", 16),
            self._snapshot("v3", 16, "postgres"),
            self._snapshot("v4", 32, "postgres"),
        ]

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli_entry(["temporal", "init", str(store)]), 0)
            for number, snapshot in enumerate(snapshots, start=1):
                self.assertEqual(
                    cli_entry(
                        [
                            "temporal",
                            "add",
                            str(store),
                            str(snapshot),
                            "-m",
                            f"version {number}",
                        ]
                    ),
                    0,
                )

        timeline_stdout = io.StringIO()
        with contextlib.redirect_stdout(timeline_stdout):
            self.assertEqual(
                cli_entry(
                    [
                        "temporal",
                        "timeline",
                        str(store),
                        "--key",
                        "database.pool_size",
                        "--file",
                        "config.json",
                        "--json",
                    ]
                ),
                0,
            )
        timeline = json.loads(timeline_stdout.getvalue())
        self.assertEqual(timeline["query"], {"key": "database.pool_size", "file": "config.json"})
        self.assertEqual(timeline["hit_count"], 3)
        self.assertTrue(timeline["all_verified"])
        self.assertEqual([row["version_id"] for row in timeline["hits"]], ["v1", "v2", "v4"])
        self.assertTrue(all(row["verification_passed"] for row in timeline["hits"]))

        evidence_stdout = io.StringIO()
        with contextlib.redirect_stdout(evidence_stdout):
            self.assertEqual(
                cli_entry(
                    [
                        "temporal",
                        "evidence",
                        str(store),
                        "--key",
                        "database.pool_size",
                        "--file",
                        "config.json",
                        "--json",
                    ]
                ),
                0,
            )
        evidence = json.loads(evidence_stdout.getvalue())
        self.assertEqual(evidence["evidence_count"], 3)
        self.assertTrue(evidence["all_verified"])
        self.assertEqual(
            [row["current_value_ref"] for row in evidence["evidence"]],
            ["4", "16", "32"],
        )


if __name__ == "__main__":
    unittest.main()
