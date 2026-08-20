# Starter GitHub Issues

These are candidate issues to create after the repository is public.

## 1. Persistent Temporal CLI State

**Problem:** Temporal state currently lives in-process; separate CLI invocations do not persist a project history.

**Scope:** define a local on-disk state format and wire persistent `add`, `list`, `timeline`, `reconstruct`, and `evidence` commands.

**Acceptance:** state survives process restart; exact reconstruction remains SHA-verified; existing tests stay green.

**Out of scope:** network/distributed storage, AI queries.

---

## 2. Rename Identity Detection

**Problem:** v0.1 represents rename as delete + add.

**Scope:** add optional deterministic rename inference without weakening add/delete semantics.

**Acceptance:** unchanged-content rename can surface as rename; exact reconstruction stays unchanged; inference can be disabled.

**Out of scope:** broad semantic similarity inference.

---

## 3. Repeated-Array Performance Profiling

**Problem:** growing-array histories show a strong scaling cliff.

**Scope:** profile the hot path first; propose a bounded optimization; preserve exact recovery and frozen benchmarks.

**Acceptance:** include before/after profiles and reproducible benchmark; 1000-transition workload must improve materially without changing correctness.

**Out of scope:** core contract redesign.

---

## 4. Signed Manifest / External Trust Anchor Design

**Problem:** v0.1 verifies integrity but does not provide signed authenticity against an attacker able to rewrite records and metadata together.

**Scope:** design document covering threat model, signing boundary, key rotation, revocation, and verification path.

**Acceptance:** design is compatible with current CAS + Evidence path and does not weaken deterministic reconstruction.

**Out of scope:** implementation in the first issue.

---

## 5. Git Connector Adversarial Tests

**Problem:** local Git support needs broader real-history edge-case coverage.

**Scope:** backdated commits, merges, identical trees, empty commits, long histories, delete/re-add, non-UTF8 file bytes where Git permits them.

**Acceptance:** each scenario has a deterministic pass or explicit documented failure; no silent fallback.

---

## 6. Third Public Real-History Benchmark Corpus

**Problem:** DevInit and Vite are too small a basis for broad conclusions.

**Scope:** add one public, reproducible structured-data history with source/provenance and frozen hashes.

**Acceptance:** corpus acquisition is documented; hashes are fixed; exact restore gate passes; negative results are retained.
