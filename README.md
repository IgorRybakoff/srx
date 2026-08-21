# SRX — Semantic Reconstructive eXchange

[![tests](https://github.com/IgorRybakoff/srx/actions/workflows/tests.yml/badge.svg)](https://github.com/IgorRybakoff/srx/actions/workflows/tests.yml)

**Exact reconstruction and version intelligence for evolving structured data.**

> **Ask the history. Prove the answer.**

SRX is an experimental open-source reconstructive engine for evolving structured data. It explores whether some version transitions can be represented as compact, reversible structural explanations while preserving exact target bytes and falling back to conventional representations when structural encoding is not cheaper.

**Status:** Public v0.1 — experimental.  
**Language:** Python >= 3.10  
**License:** Apache-2.0

SRX is not a universal compressor, Git replacement, cloud storage product, or AI-first system. The deterministic core has no LLM dependency.

## How it works

```text
                 Existing data
          JSON / folders / local Git
                    │
                    ▼
             Source Connector
                    │
                    ▼
          ┌──────────────────┐
          │     SRX Core     │
          │ transformations  │
          │ exact residual   │
          │ cost selector    │
          │ reconstruction   │
          │ SHA verification │
          └────────┬─────────┘
                   │
                   ▼
             Temporal Index
                   │
          ┌────────┴─────────┐
          ▼                  ▼
     Historical         Selective
       Queries         Reconstruction
          │                  │
          └────────┬─────────┘
                   ▼
             EvidenceResolver
                   │
                   ▼
         Exact source + SHA evidence
```

## What works today

- deterministic JSON structural transformations;
- string-delta, sequence edit candidates, sparse formatting residuals;
- adaptive structural-vs-conventional selection in the public core API;
- exact target reconstruction with target-size and SHA-256 verification;
- explicit errors for corrupted, missing, or mismatched references;
- Core CLI: `srx diff`, `srx reconstruct`, `srx verify`, `srx stats`;
- Temporal/Evidence Python layer with causal parent-before-child ordering;
- nested JSON key timelines;
- file-level selective historical reconstruction;
- verified evidence resolution through reconstruction + independent source SHA-256;
- local-folder and local-Git connectors.

A persistent multi-command Temporal CLI is **not** shipped in v0.1.

## Quickstart

After cloning the repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

### Core CLI

```bash
srx diff demo/part_a_core_cli/snapshots/v1/config.json \
         demo/part_a_core_cli/snapshots/v2/config.json \
         -o /tmp/v1_v2.srx

srx reconstruct /tmp/v1_v2.srx \
         --ref demo/part_a_core_cli/snapshots/v1/config.json \
         -o /tmp/restored_v2.json

srx verify /tmp/v1_v2.srx \
         --ref demo/part_a_core_cli/snapshots/v1/config.json

srx stats /tmp/v1_v2.srx
```

For a reproducible end-to-end run, see [`demo/`](demo/README.md).

Observed release-demo checks:

```text
Exact Verification  : PASS (SHA-256 matched)
VERIFICATION RESULT: [ PASS ] Exact match verified.
PASS: restored_v2.json is byte-for-byte identical to v2/config.json
```

## Temporal / Evidence API

The Temporal/Evidence layer is currently a Python API. The checked-in demo uses the real production SRX core, not a stub:

```bash
python demo/part_b_temporal_api/run.py
```

It builds four local snapshot versions, queries the nested key `database.pool_size`, reconstructs exactly `v3/config.json`, and returns evidence only after SHA-256 verification.

## Measured real-history benchmark gate

These are frozen v0.9 compatibility results. They are not claims of universal superiority.

| Corpus | Conventional | Structural-only | SRX adaptive | Structural selected | Exact restore |
|---|---:|---:|---:|---:|---|
| DevInit — 6 versions / 5 transitions | 1638 B | 1881 B | 1638 B | 0/5 | PASS |
| Vite — 10 versions / 9 transitions | 2952 B | 3025 B | 2919 B | 4/9 | PASS |

- **DevInit:** no gain over the strongest conventional baseline.
- **Vite:** ~1.12% cumulative gain; ~2.85% transition-only gain.

Frozen expected values are in [`benchmarks/results/frozen_v0.9_expected.json`](benchmarks/results/frozen_v0.9_expected.json), and corpus hashes are in [`benchmarks/FROZEN_CORPUS_SHA256.txt`](benchmarks/FROZEN_CORPUS_SHA256.txt).

## Integrity and trust model

Standalone SRX records verify framing, reference requirements, target size, and reconstructed SHA-256 against metadata stored in the record. This is an integrity check, not a signed authenticity guarantee.

The integrated Temporal/Evidence path adds a content-addressed representation digest and an independent historical source-file SHA-256. `EvidenceResolver` returns verified evidence only after actual reconstruction and SHA verification.

See [`TRUST_MODEL.md`](TRUST_MODEL.md).

## Known limitations

Important current limitations include:

- repeated growing-array histories have a measured performance cliff;
- rename identity is represented as deterministic delete + add;
- selective reconstruction is guaranteed at file level, not physical subtree level;
- persistent Temporal CLI is not complete;
- no signed manifests/MAC in v0.1;
- only local-folder and local-Git connectors are shipped.

See [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md).

## Tests and benchmarks

```bash
python tests/run_all_tests.py
python benchmarks/verify_corpus_hashes.py
python benchmarks/verify_frozen_regression.py
```

The public release gate expects **55 unit/integration tests** plus the benchmark regression checks to pass.

## Project naming

- **SRX** — Semantic Reconstructive eXchange: deterministic core + temporal/evidence foundation.
- **SRX Intelligence** — name reserved for the future user-facing product layer; it is not an AI dependency of v0.1.

## Roadmap and contributing

- [`ROADMAP.md`](ROADMAP.md)
- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md)
- [`BENCHMARK_ENVIRONMENT.md`](BENCHMARK_ENVIRONMENT.md)
- [`docs/VALIDATION.md`](docs/VALIDATION.md)

## License

Apache-2.0. See [`LICENSE`](LICENSE).
