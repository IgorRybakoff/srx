# SRX Roadmap

This roadmap separates shipped behavior from candidates. It is not a promise.

## Direction

SRX is currently developed as a **version intelligence and verified reconstruction engine** for evolving structured data.

The primary product hypothesis is not universal compression. Structural and delta representations remain implementation mechanisms inside the reconstructive core. The near-term question is whether SRX can make historical state easier to query, reconstruct, and prove with deterministic evidence.

> **Ask the history. Prove the answer.**

## v0.1 — current public baseline

- deterministic reconstructive core;
- JSON structural adapter;
- exact reconstruction with target size + SHA-256 verification;
- conventional snapshot/patch fallback plus experimental structural representation selection;
- Core CLI (`diff`, `reconstruct`, `verify`, `stats`);
- Temporal/Evidence Python layer;
- persistent Temporal CLI (`init`, `add`, `list`, `timeline`, `reconstruct`, `evidence`);
- persistent temporal metadata + CAS references across process restarts;
- local-folder and local-Git connectors;
- nested JSON key timeline;
- file-level selective reconstruction;
- evidence verification through exact reconstruction + independent source SHA-256;
- deterministic parent-before-child causal ordering;
- end-to-end Temporal CLI demo in CI;
- real-Git-history demo against the SRX repository itself;
- pinned Vite v7.1.0 50-commit demo with verified nested-key history and byte-perfect historical reconstruction;
- frozen DevInit/Vite regression gate.

## v0.1.x — near term

- README/demo polish around the version-intelligence workflow;
- third public real-history benchmark corpus;
- more connector adversarial tests;
- clearer machine-readable CLI output for temporal/evidence queries;
- packaging cleanup for normal Python distribution.

## v0.2 candidates

- stronger temporal query UX;
- rename identity detection;
- checkpoint strategy for long histories;
- repeated-array performance optimization;
- additional deterministic format adapters;
- stronger authenticity / signed-manifest design;
- additional source connectors;
- optional higher-level natural-language query planner outside the deterministic core.

## Evidence policy

- exact reconstruction claims require byte-for-byte verification;
- evidence must be re-verified after persistence reload;
- benchmark regressions remain frozen and reproducible;
- negative benchmark results are retained rather than hidden;
- representation/compression results are not generalized beyond measured workloads.

## Explicit non-goals

- universal-compressor positioning;
- claiming that SRX generally beats zstd/xdelta/bsdiff-style approaches;
- replacing Git;
- putting an LLM inside the deterministic encode/decode path;
- claiming signed provenance before an external trust anchor exists;
- broad cloud/distributed-storage promises in v0.1.
