"""Reproduce and verify the frozen v0.9 compatibility metrics.

The frozen baseline was recorded with the external zstd CLI available.
This verifier fails explicitly if zstd is missing so benchmark semantics do
not silently change to the portable zlib fallback.
"""

from __future__ import annotations

import json
import shutil

from run_benchmarks import ROOT, run_corpus_benchmark

EXPECTED_PATH = ROOT / "benchmarks" / "results" / "frozen_v0.9_expected.json"


def run_actual() -> dict:
    devinit = sorted((ROOT / "benchmarks" / "corpora" / "devinit").glob("devinit.schema-*.json"))
    vite = sorted((ROOT / "benchmarks" / "corpora" / "vite").glob("v*.json"))
    return {
        "devinit": run_corpus_benchmark("devinit", devinit),
        "vite": run_corpus_benchmark("vite", vite),
    }


def check_corpus(name: str, expected: dict, actual: dict) -> list[str]:
    problems: list[str] = []
    exact_pairs = {
        "versions": "versions_count",
        "transitions": "transitions_count",
        "first_snapshot_bytes": "first_snapshot_bytes",
        "conventional_cumulative_bytes": "conventional_cumulative_bytes",
        "structural_only_cumulative_bytes": "structural_only_cumulative_bytes",
        "srx_adaptive_cumulative_bytes": "srx_adaptive_cumulative_bytes",
        "structural_selected": "structural_selected_count",
        "exact_restore": "all_exact_restore_verified",
    }
    for exp_key, act_key in exact_pairs.items():
        if expected[exp_key] != actual[act_key]:
            problems.append(
                f"{name}.{exp_key}: expected {expected[exp_key]!r}, got {actual[act_key]!r}"
            )

    percent_pairs = {
        "gain_percent": "total_gain_percent",
        "transition_only_gain_percent": "transition_gain_percent",
    }
    for exp_key, act_key in percent_pairs.items():
        if round(float(expected[exp_key]), 2) != round(float(actual[act_key]), 2):
            problems.append(
                f"{name}.{exp_key}: expected {expected[exp_key]!r}, got {actual[act_key]!r}"
            )
    return problems


def main() -> int:
    zstd = shutil.which("zstd")
    if zstd is None:
        print("FROZEN REGRESSION: ERROR — external zstd CLI is required for this baseline")
        return 2

    expected = json.loads(EXPECTED_PATH.read_text())
    actual = run_actual()
    problems: list[str] = []
    for name in ("devinit", "vite"):
        problems.extend(check_corpus(name, expected[name], actual[name]))

    if problems:
        print("FROZEN REGRESSION: FAIL")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print("FROZEN REGRESSION: PASS")
    print(f"zstd: {zstd}")
    print("DevInit: conventional=1638 B, SRX=1638 B, structural=0/5, exact=True")
    print("Vite: conventional=2952 B, SRX=2919 B, structural=4/9, exact=True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
