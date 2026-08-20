# SRX Public v0.1 — Trust Model

SRX distinguishes **integrity** from **authenticity**.

## Standalone core record

`SRXCoreAPI.reconstruct(reference, representation)` verifies:

- record framing/length;
- reference requirements;
- reconstructed target size;
- reconstructed target SHA-256 against the target hash embedded in the SRX record.

This detects accidental corruption and ordinary payload tampering when the stored target hash remains authoritative.

It does **not** by itself authenticate a maliciously rewritten record in which an attacker can modify both payload and the embedded target hash/size consistently.

## Integrated Temporal / Evidence path

The public v0.1 integrated path adds independent checks:

1. SRX representation bytes are stored in a content-addressed CAS using `sha256:<record_digest>`.
2. CAS retrieval recomputes the record digest and rejects any mismatch.
3. `FileEntry.sha256` stores the expected source-file SHA-256 independently of the SRX record header.
4. `SelectiveReconstructor` reconstructs the requested historical file and verifies it against `FileEntry.sha256`.
5. `EvidenceResolver` returns `verification_passed=True` only after that reconstruction and SHA-256 verification succeeds.

Thus, the Evidence path has an external integrity anchor beyond the SRX record's embedded target hash.

## Out of scope for v0.1

Cryptographic authenticity against an attacker who can rewrite the repository metadata, CAS index, manifests, and records together requires a signed manifest, MAC, trusted external digest, or equivalent trust anchor. That is future hardening and is not claimed by v0.1.
