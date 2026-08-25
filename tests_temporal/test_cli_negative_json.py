from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from srx.cli.main import cli_entry
from srx_temporal.persistence import load_index


class TemporalJsonNegativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.store = self.tmp / "store"
        self.snapshot = self.tmp / "snapshot"
        self.snapshot.mkdir(parents=True)
        (self.snapshot / "config.json").write_text(
            json.dumps({"database": {"pool_size": 16}}, indent=2) + "\n",
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _init_one_version(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli_entry(["temporal", "init", str(self.store)]), 0)
            self.assertEqual(
                cli_entry(
                    [
                        "temporal",
                        "add",
                        str(self.store),
                        str(self.snapshot),
                        "-m",
                        "initial",
                    ]
                ),
                0,
            )

    def test_json_unknown_key_returns_valid_empty_result(self):
        self._init_one_version()

        for command, count_field, rows_field in (
            ("timeline", "hit_count", "hits"),
            ("evidence", "evidence_count", "evidence"),
        ):
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = cli_entry(
                    [
                        "temporal",
                        command,
                        str(self.store),
                        "--key",
                        "database.missing_key",
                        "--file",
                        "config.json",
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(stderr.getvalue(), "")
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload[count_field], 0)
            self.assertEqual(payload[rows_field], [])
            self.assertTrue(payload["all_verified"])

    def test_json_evidence_fails_closed_when_cas_object_is_corrupt(self):
        self._init_one_version()

        loaded = load_index(self.store)
        entry = loaded.list_versions()[0].files[0]
        self.assertTrue(entry.representation_ref.startswith("sha256:"))
        digest = entry.representation_ref.split(":", 1)[1]
        cas_path = loaded.cas.root / digest[:2] / digest[2:]
        cas_path.write_bytes(b"present-but-corrupt")

        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli_entry(
                [
                    "temporal",
                    "evidence",
                    str(self.store),
                    "--key",
                    "database.pool_size",
                    "--file",
                    "config.json",
                    "--json",
                ]
            )

        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("representation is corrupt", stderr.getvalue())
        self.assertNotIn("verification_passed", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
