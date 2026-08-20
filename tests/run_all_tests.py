"""Master test runner for SRX Public v0.1.

Runs both the deterministic core suite and the Temporal/Evidence integration suite.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_suite() -> unittest.TestSuite:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.discover(str(ROOT / "tests"), pattern="test_*.py", top_level_dir=str(ROOT)))
    suite.addTests(loader.discover(str(ROOT / "tests_temporal"), pattern="test_*.py", top_level_dir=str(ROOT)))
    return suite


if __name__ == "__main__":
    suite = load_suite()
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
