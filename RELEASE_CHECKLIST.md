# SRX Public v0.1 Release Checklist

## Correctness

- [ ] `python tests/run_all_tests.py` passes all core + temporal tests.
- [ ] `python benchmarks/verify_frozen_regression.py` reproduces and matches frozen DevInit/Vite values.
- [ ] `benchmarks/FROZEN_CORPUS_SHA256.txt` matches the checked-in corpora.
- [ ] Demo Part A runs from a clean environment.
- [ ] Demo Part B runs with `make_production_core()` and produces verified evidence.

## Documentation

- [ ] README contains only implemented commands and APIs.
- [ ] README contains no fabricated benchmark or performance numbers.
- [ ] `KNOWN_LIMITATIONS.md` is linked.
- [ ] `TRUST_MODEL.md` is linked.
- [ ] `BENCHMARK_ENVIRONMENT.md` is linked.
- [ ] No persistent Temporal CLI is claimed as shipped.
- [ ] No signed authenticity is claimed as shipped.

## Packaging

- [ ] `LICENSE` is present and Apache-2.0 matches `pyproject.toml`.
- [ ] package version is `0.1.0`.
- [ ] clean editable install works in a fresh venv.
- [ ] `srx --help` works after installation.
- [ ] no `__pycache__`, `.pytest_cache`, `*.egg-info`, build artifacts or local `.srx` outputs are committed.

## Public repository hygiene

- [ ] no internal coordination artifacts;
- [ ] no obsolete integration/review artifacts;
- [ ] no private roadmap documents;
- [ ] no credentials, API keys, tokens or personal email addresses.
