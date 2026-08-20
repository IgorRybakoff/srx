# SRX Public v0.1 — Known Limitations

These are documented scope/performance limitations, not hidden failures.

## 1. Repeated growing-array history

Observed exact runs in the public v0.1 gate environment:

| Sequential transitions | Result |
|---:|---|
| 100 | exact, ~2.9 s |
| 200 | exact, ~6.4 s |
| 300 | exact, ~9.8 s |
| 500 | exact, ~20.7 s |
| 1000 | did not finish within a 120 s performance gate |

All completed transitions reconstructed exactly and passed SHA-256 verification.
The 1000-transition result is classified as a performance limitation, not a correctness failure.

Planned hardening: sequence-edit optimization and/or periodic checkpoints for pathological long histories.

## 2. Rename identity

v0.1 does not infer stable logical identity across a rename. A rename is represented deterministically as delete + add.

## 3. Reconstruction granularity

v0.1 guarantees selective reconstruction at file level. It does not promise subtree-only physical reconstruction.

## 4. Connectors

v0.1 focuses on local folder and local Git sources. S3, SharePoint, and distributed storage connectors are future work.

## 5. AI

No LLM is part of the deterministic core. Natural-language query planning is future/optional product work.

## 6. Cryptographic authenticity

The standalone SRX record format verifies reconstructed bytes against the target SHA-256 embedded in the record. It does not claim cryptographic authenticity if an attacker can rewrite both record payload and header consistently.

The integrated Temporal/Evidence path adds a content-addressed record digest plus an independent source-file SHA-256. Signed manifests / MACs are future hardening. See `TRUST_MODEL.md`.
