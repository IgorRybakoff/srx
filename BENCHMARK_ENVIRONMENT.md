# SRX Public v0.1 — Benchmark Environment

Frozen v0.9 regression is checked against:

- `benchmarks/results/frozen_v0.9_expected.json`
- `benchmarks/FROZEN_CORPUS_SHA256.txt`

Recorded public v0.1 compatibility-gate environment:

- OS: Linux 6.18.35 x86_64 (glibc 2.41)
- Python: 3.13.5
- Architecture: x86_64
- Available RAM: ~6.37 GB
- External `zstd`: **available**, CLI v1.5.7

The frozen `1638 B / 2919 B` compatibility values use the external zstd path. If `zstd` is unavailable, SRX has a portable zlib fallback, but byte-size benchmark results are not expected to match this frozen baseline.

`benchmarks/verify_frozen_regression.py` therefore requires an external `zstd` binary and fails explicitly when it is missing. Performance timings remain environment-dependent; frozen sizes and exact-reconstruction results are the compatibility gate.
