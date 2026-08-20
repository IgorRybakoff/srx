# Contributing to SRX

SRX is an experimental exact-reconstruction project. Correctness and reproducibility take priority over feature count.

## Setup

Requirements: Python >= 3.10.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Run the full test gate

```bash
python tests/run_all_tests.py
```

The runner executes both `tests/` and `tests_temporal/`.

## Run benchmarks

```bash
python benchmarks/verify_corpus_hashes.py
python benchmarks/verify_frozen_regression.py
```

Frozen expected values:

- `benchmarks/results/frozen_v0.9_expected.json`
- `benchmarks/FROZEN_CORPUS_SHA256.txt`

## Non-negotiable rules

1. Exact reconstruction must remain bit-for-bit correct.
2. Every representation path must preserve target SHA-256 exact recovery.
3. Integrity failures must fail explicitly; silent integrity fallback is a bug.
4. Benchmark claims require reproducible scripts and checked-in corpus hashes.
5. Frozen benchmark/corpus changes must be intentional and documented.
6. Temporal/Evidence code must consume the core through its public boundary; do not bypass integrity checks.
7. No LLM dependency belongs inside the deterministic core.

## Good contribution areas

- adversarial tests;
- documentation fixes;
- Git connector edge cases;
- new benchmark corpora;
- performance profiling that preserves exact reconstruction;
- format adapters with deterministic round-trip behavior.

## Pull requests

A PR should include:

- a focused description of the problem;
- tests for changed behavior;
- benchmark impact when relevant;
- confirmation that `python tests/run_all_tests.py` passes;
- no fabricated performance or storage claims.

## Security / integrity reports

A path that can return verified evidence without reconstruction + SHA-256 verification is a high-severity defect. Please report such cases with the smallest reproducible example possible.

SRX v0.1 does not claim signed cryptographic authenticity; see `TRUST_MODEL.md`.

## License

Contributions are accepted under the Apache-2.0 License.
