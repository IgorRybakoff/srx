# Public Claim Audit

| Public claim | Evidence | Safe wording | Avoid |
|---|---|---|---|
| Exact reconstruction | reconstruction size + SHA gates and tests | "reconstructs exact target bytes and verifies SHA-256" | "cryptographically authentic" |
| Version intelligence | TemporalIndex + nested key timeline | "deterministic temporal queries over indexed histories" | "understands your data" |
| Adaptive selection | `SRXCoreAPI.encode()` candidate selection | "selects the cheapest exact candidate among implemented representations" | "always compresses better" |
| DevInit result | frozen benchmark | "matches conventional baseline: 1638 B vs 1638 B" | "beats conventional" |
| Vite result | frozen benchmark | "~1.12% cumulative gain on this corpus" | "beats Git/Zstd generally" |
| Evidence verification | SelectiveReconstructor + EvidenceResolver | "verified only after reconstruction + independent source SHA" | "signed provenance" |
| Selective reconstruction | file-level reconstructor | "file-level selective reconstruction" | "arbitrary subtree materialization" |
| Git support | local Git connector | "local Git repository connector" | "GitHub/cloud integration" |
| AI | no LLM in core | "AI is not required for deterministic core" | "AI-powered core" |
