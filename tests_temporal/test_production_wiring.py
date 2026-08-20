"""
Integration test: wires SelectiveReconstructor through ThinCoreAdapter
against a conformance double of the declared production contract:

    SRXCoreAPI.reconstruct(reference: bytes | None, representation: bytes) -> bytes
    SRXCoreAPI.verify(reconstructed: bytes, expected_sha256: str) -> bool

IMPORTANT — scope of what this actually proves:
`srx.public_api.SRXCoreAPI` (the real core) is not importable in this
environment — only its signature was provided, not its code. This
double is NOT the real core. It reproduces only the declared method
names/signatures (including reference being Optional) so that the
*wiring* — make_production_core()'s import/adapt path, ThinCoreAdapter
attribute forwarding, and reconstructor.py passing None instead of b""
for no-reference entries — is exercised exactly as it would be against
the real object. It says nothing about the real core's actual
transformation/residual/cost behavior.

`class _FakeSRXCoreAPI` deliberately mimics only the public shape
(method names, argument types/order) — its internal behavior is the
same identity/full-copy placeholder as StubCoreReconstructor, because
no real encoding algorithm was provided to this workstream either.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from srx_temporal.cas import ContentAddressableStore, sha256_hex
from srx_temporal.connectors.local_folder import LocalFolderConnector
from srx_temporal.core_adapter import ThinCoreAdapter
from srx_temporal.ingest import ingest_snapshot
from srx_temporal.reconstructor import SelectiveReconstructor
from srx_temporal.temporal_index import TemporalIndex


class _FakeSRXCoreAPI:
    """
    Conformance double for srx.public_api.SRXCoreAPI's declared public
    contract. Same method names as the real class (so ThinCoreAdapter's
    default attr names apply unchanged), same argument shape
    (reference: bytes | None). NOT the real core — see module docstring.
    """

    def reconstruct(self, reference: bytes | None, representation: bytes) -> bytes:
        # Placeholder behavior only — real encoding was never provided
        # to this workstream (see ingest.py module docstring for the
        # matching caveat on the encode side).
        return representation

    def verify(self, reconstructed: bytes, expected_sha256: str) -> bool:
        return sha256_hex(reconstructed) == expected_sha256


class ProductionWiringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cas = ContentAddressableStore(self.tmp / "cas")
        self.index = TemporalIndex(self.cas)
        self.connector = LocalFolderConnector()
        # Exactly the wiring make_production_core() performs, minus the
        # unavailable `from srx.public_api import SRXCoreAPI` import.
        real_core = _FakeSRXCoreAPI()
        self.core = ThinCoreAdapter(real_core, reconstruct_attr="reconstruct",
                                     verify_attr="verify")
        self.recon = SelectiveReconstructor(self.index, self.cas, self.core)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_thin_adapter_forwards_calls_correctly(self):
        root = self.tmp / "snap"
        root.mkdir()
        (root / "config.json").write_text(json.dumps({"replicas": 2}))
        self.connector.register_snapshot("v0", root, timestamp="2026-07-01T00:00:00+00:00")
        ingest_snapshot(self.index, self.cas, self.connector, "v0")

        result = self.recon.reconstruct_file("v0", "config.json")
        self.assertTrue(result.verification_passed)
        self.assertEqual(json.loads(result.bytes_data)["replicas"], 2)

    def test_no_reference_entry_passes_none_not_empty_bytes(self):
        """
        SRXCoreAPI's contract types `reference` as bytes | None.
        For a full-snapshot entry (no reference_version_id), the
        adapter must pass None through — not b"" — since that
        distinction is meaningful to a real core implementation.
        """
        captured = {}
        real_core = _FakeSRXCoreAPI()
        original = real_core.reconstruct

        def spy(reference, representation):
            captured["reference"] = reference
            return original(reference, representation)

        real_core.reconstruct = spy
        core = ThinCoreAdapter(real_core)
        recon = SelectiveReconstructor(self.index, self.cas, core)

        root = self.tmp / "snap2"
        root.mkdir()
        (root / "a.json").write_text("{}")
        self.connector.register_snapshot("v1", root, timestamp="2026-07-02T00:00:00+00:00")
        ingest_snapshot(self.index, self.cas, self.connector, "v1")

        recon.reconstruct_file("v1", "a.json")
        self.assertIsNone(captured["reference"])


if __name__ == "__main__":
    unittest.main()
