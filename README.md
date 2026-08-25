# SRX — Semantic Reconstructive eXchange

[![tests](https://github.com/IgorRybakoff/srx/actions/workflows/tests.yml/badge.svg)](https://github.com/IgorRybakoff/srx/actions/workflows/tests.yml)

**Version intelligence and verified reconstruction for evolving structured data.**

> **Ask the history. Prove the answer.**

SRX is an experimental open-source engine for querying how structured data changed over time and reconstructing the exact historical source behind an answer.

The current product direction is **version intelligence first**: temporal queries, selective historical reconstruction, and evidence that is re-verified against exact bytes. Structural/delta representations remain implementation mechanisms inside the reconstructive core; SRX does **not** claim to be a universal compressor or to beat conventional delta encoding in general.

**Status:** Public v0.1 — experimental.  
**Language:** Python >= 3.10  
**License:** Apache-2.0

SRX is not a Git replacement, cloud storage product, signed provenance system, or AI-first runtime. The deterministic core has no LLM dependency.

## Why SRX

Versioned systems can usually answer *what is the current value?* SRX is exploring a narrower question:

> **Can a developer ask what changed, when it changed, reconstruct the exact historical source, and verify the evidence in one deterministic path?**

Examples:

```text
When did database.pool_size change?
Which historical version proves that change?
Can I reconstruct exactly that config.json?
Does the reconstructed file still match its recorded SHA-256?
```

The intended value is not compression by itself. Compression/delta selection is useful only insofar as it supports an exact, bounded, inspectable historical state layer.

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
          │ representations  │
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

- deterministic exact reconstruction with target-size and SHA-256 verification;
- content-addressed SRX representations;
- conventional snapshot/patch fallback plus experimental structural representations;
- explicit failures for corrupted, missing, or mismatched references;
- causal parent-before-child temporal ordering;
- nested JSON key timelines;
- file-level selective historical reconstruction;
- evidence resolution through actual reconstruction + independent source SHA-256;
- persistent temporal state across process restarts;
- local-folder and local-Git connectors;
- Core CLI: `srx diff`, `srx reconstruct`, `srx verify`, `srx stats`;
- Persistent Temporal CLI: `init`, `add`, `list`, `timeline`, `reconstruct`, `evidence`.

## Quickstart

After cloning the repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

### Persistent Temporal CLI

Initialize a store and add snapshots:

```bash
srx temporal init ./history

srx temporal add ./history ./snapshots/v1 -m "initial config"
srx temporal add ./history ./snapshots/v2 -m "tune pool size"
srx temporal add ./history ./snapshots/v3 -m "switch database"
```

Inspect the committed history:

```bash
srx temporal list ./history
```

Query the timeline of a nested key:

```bash
srx temporal timeline ./history \
  --key database.pool_size \
  --file config.json
```

Resolve verified evidence for the same key:

```bash
srx temporal evidence ./history \
  --key database.pool_size \
  --file config.json
```

Selectively reconstruct one historical file:

```bash
srx temporal reconstruct ./history v3 \
  --file config.json \
  -o restored_v3.json
```

The checked-in end-to-end demo runs this path with the real SRX core:

```bash
bash demo/run_temporal_demo.sh
```

The CI demo verifies that the reconstructed historical file is byte-for-byte identical to the original and that SHA-256 verification passes.

### Core CLI

The lower-level record CLI remains available:

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

## Persistence and evidence semantics

The persistent temporal manifest stores immutable temporal metadata and CAS references. Representation bytes remain in `<store>/cas`.

Evidence is **not** serialized as trusted state. After reload, constructing the selective reconstructor re-binds the evidence resolver, and timeline/evidence queries perform reconstruction and SHA-256 verification again before returning verified evidence.

This keeps persistence from turning a previous `verification_passed=True` flag into an authority by itself.

## Measured representation benchmark gate

These frozen v0.9 compatibility results are kept as regression evidence, not as a product claim of compression superiority.

| Corpus | Conventional | Structural-only | SRX adaptive | Structural selected | Exact restore |
|---|---:|---:|---:|---:|---|
| DevInit — 6 versions / 5 transitions | 1638 B | 1881 B | 1638 B | 0/5 | PASS |
| Vite — 10 versions / 9 transitions | 2952 B | 3025 B | 2919 B | 4/9 | PASS |

- **DevInit:** no gain over the conventional baseline.
- **Vite:** ~1.12% cumulative gain; ~2.85% transition-only gain.
- Structural representation is therefore treated as an experimental mechanism, not the central value proposition of SRX.

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
- no signed manifests/MAC in v0.1;
- only local-folder and local-Git connectors are shipped;
- natural-language historical queries are not part of the deterministic core.

See [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md).

## Tests and reproducibility

```bash
python tests/run_all_tests.py
bash demo/run_temporal_demo.sh
python benchmarks/verify_corpus_hashes.py
python benchmarks/verify_frozen_regression.py
```

The current public gate contains **57 unit/integration tests**. CI runs on Python 3.10 and 3.13, executes the Temporal CLI demo, verifies 16 frozen corpus hashes, and checks the frozen benchmark regression.

## Project direction

The near-term SRX track is:

```text
Version Intelligence
    ↓
Persistent temporal history
    ↓
Nested-key timelines
    ↓
Selective exact reconstruction
    ↓
Verified evidence
    ↓
Real-project demos and additional connectors
```

The project will continue to publish negative benchmark results when a representation does not outperform a conventional baseline. Compression is a mechanism; exact historical answers with verifiable evidence are the primary product hypothesis.

## Project naming

- **SRX** — Semantic Reconstructive eXchange: deterministic reconstructive core + temporal/evidence engine.
- **SRX Intelligence** — name reserved for a future higher-level query/product layer; it is not an AI dependency of v0.1.

## Roadmap and contributing

- [`ROADMAP.md`](ROADMAP.md)
- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md)
- [`BENCHMARK_ENVIRONMENT.md`](BENCHMARK_ENVIRONMENT.md)
- [`docs/VALIDATION.md`](docs/VALIDATION.md)

## License

Apache-2.0. See [`LICENSE`](LICENSE).
