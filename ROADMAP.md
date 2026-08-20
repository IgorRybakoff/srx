# SRX Roadmap

This roadmap separates shipped behavior from candidates. It is not a promise.

## v0.1 — current public baseline

- deterministic reconstructive core;
- JSON structural adapter;
- exact reconstruction with target size + SHA-256 verification;
- adaptive structural/conventional selection in the public core API;
- Core CLI (`diff`, `reconstruct`, `verify`, `stats`);
- Temporal/Evidence Python layer;
- local-folder and local-Git connectors;
- nested JSON key timeline;
- file-level selective reconstruction;
- evidence verification through exact reconstruction + independent source SHA-256;
- deterministic parent-before-child causal ordering;
- frozen DevInit/Vite regression gate.

## v0.1.x — near term

- persistent Temporal CLI state and commands;
- installation and demo polish;
- more connector adversarial tests;
- third public real-history benchmark corpus;
- packaging cleanup for normal Python distribution.

## v0.2 candidates

- rename identity detection;
- checkpoint strategy for long histories;
- repeated-array performance optimization;
- additional deterministic format adapters;
- stronger authenticity / signed-manifest design;
- additional source connectors.

## Explicit non-goals

- universal-compressor positioning;
- replacing Git;
- putting an LLM inside the deterministic encode/decode path;
- claiming signed provenance before an external trust anchor exists;
- broad cloud/distributed-storage promises in v0.1.
