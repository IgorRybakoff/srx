from pathlib import Path
import shutil
import tempfile
import unittest

from srx.public_api import SRXCoreAPI
from srx.core.compression import zpatch
from srx.core.constants import REC_ZSTD_PATCH
from srx.core.record import create_record
from srx_temporal.cas import ContentAddressableStore, sha256_hex
from srx_temporal.core_adapter import make_production_core
from srx_temporal.models import FileEntry, VersionManifest
from srx_temporal.reconstructor import SelectiveReconstructor
from srx_temporal.temporal_index import TemporalIndex


class RedTeamHardeningTests(unittest.TestCase):
    def test_record_trailing_bytes_rejected(self):
        ref = b'{"a":1}\n'
        tgt = b'{"a":2}\n'
        rec = SRXCoreAPI.encode(ref, tgt)
        with self.assertRaisesRegex(ValueError, "trailing bytes"):
            SRXCoreAPI.reconstruct(ref, rec + b"JUNK")

    def test_1100_reference_chain_reconstructs_iteratively(self):
        root = Path(tempfile.mkdtemp())
        try:
            cas = ContentAddressableStore(root / "cas")
            index = TemporalIndex(cas)
            core = make_production_core()
            recon = SelectiveReconstructor(index, cas, core)
            previous = None
            count = 1100
            for i in range(count):
                target = f'{{"x":{i}}}'.encode()
                if previous is None:
                    representation = SRXCoreAPI.encode(None, target)
                    ref_version = None
                else:
                    representation = create_record(
                        previous, target, REC_ZSTD_PATCH, zpatch(previous, target)
                    )
                    ref_version = f"v{i-1}"
                representation_ref = cas.put(representation)
                entry = FileEntry(
                    path="config.json",
                    sha256=sha256_hex(target),
                    size_bytes=len(target),
                    media_type="application/json",
                    representation_ref=representation_ref,
                    reference_version_id=ref_version,
                )
                manifest = VersionManifest(
                    version_id=f"v{i}",
                    timestamp=f"2026-01-01T00:00:{i % 60:02d}+00:00",
                    parent_ids=((f"v{i-1}",) if i else ()),
                    message=None,
                    files=(entry,),
                )
                index.add_version(manifest, [], [])
                previous = target

            restored = recon.reconstruct_file(f"v{count-1}", "config.json")
            self.assertTrue(restored.verification_passed)
            self.assertEqual(restored.bytes_data, previous)
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
