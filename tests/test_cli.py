"""Tests for SRX Command Line Interface (CLI)."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from srx.cli.main import cli_entry


class TestCLI(unittest.TestCase):
    """Verify CLI commands: diff, reconstruct, verify, stats."""

    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.td.name)
        
        self.v1_path = self.tmp_dir / "v1.json"
        self.v2_path = self.tmp_dir / "v2.json"
        self.record_path = self.tmp_dir / "diff.srx"
        self.reconstruct_path = self.tmp_dir / "restored.json"
        
        self.v1_path.write_text('{\n  "app": "srx",\n  "version": "0.1.0",\n  "features": ["diff"]\n}\n')
        self.v2_path.write_text('{\n  "app": "srx",\n  "version": "0.2.0",\n  "features": ["diff", "verify"]\n}\n')

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_cli_diff_and_stats(self) -> None:
        # Run diff to create record
        exit_code = cli_entry([
            "diff",
            str(self.v1_path),
            str(self.v2_path),
            "-o",
            str(self.record_path),
            "--json",
        ])
        self.assertEqual(exit_code, 0)
        self.assertTrue(self.record_path.exists())

        # Run stats
        exit_code = cli_entry([
            "stats",
            str(self.record_path),
            "--json",
        ])
        self.assertEqual(exit_code, 0)

    def test_cli_reconstruct_and_verify(self) -> None:
        # 1. Create record
        cli_entry([
            "diff",
            str(self.v1_path),
            str(self.v2_path),
            "-o",
            str(self.record_path),
        ])

        # 2. Reconstruct
        exit_code = cli_entry([
            "reconstruct",
            str(self.record_path),
            "--ref",
            str(self.v1_path),
            "-o",
            str(self.reconstruct_path),
            "--json",
        ])
        self.assertEqual(exit_code, 0)
        self.assertTrue(self.reconstruct_path.exists())
        self.assertEqual(self.reconstruct_path.read_text(), self.v2_path.read_text())

        # 3. Verify
        exit_code = cli_entry([
            "verify",
            str(self.record_path),
            "--ref",
            str(self.v1_path),
            "--json",
        ])
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
