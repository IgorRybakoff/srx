# SRX Public v0.1 — Validation Summary

This page records the reproducible public release gate.

## Test suite

```bash
python tests/run_all_tests.py
```

Observed result:

```text
Ran 55 tests
OK
```

The runner includes both deterministic core tests and Temporal/Evidence integration tests.

## Frozen corpus hashes

```bash
python benchmarks/verify_corpus_hashes.py
```

Observed result:

```text
PASS: 16 frozen corpus files match SHA-256 manifest
```

## Frozen v0.9 regression

Requires the external `zstd` CLI used by the baseline.

```bash
python benchmarks/verify_frozen_regression.py
```

Observed result:

```text
FROZEN REGRESSION: PASS
DevInit: conventional=1638 B, SRX=1638 B, structural=0/5, exact=True
Vite: conventional=2952 B, SRX=2919 B, structural=4/9, exact=True
```

See `BENCHMARK_ENVIRONMENT.md` for environment details.

## Demo gates

Core CLI demo:

```bash
bash demo/part_a_core_cli/run.sh
```

Key observed checks:

```text
Exact Verification  : PASS (SHA-256 matched)
VERIFICATION RESULT: [ PASS ] Exact match verified.
PASS: restored_v2.json is byte-for-byte identical to v2/config.json
```

Temporal/Evidence demo:

```bash
python demo/part_b_temporal_api/run.py
```

Key observed checks:

```text
v1: key_added None -> 4 verified=True
v2: value_changed 4 -> 16 verified=True
v4: value_changed 16 -> 32 verified=True
verification_passed=True
byte_equal_to_original=True
```
