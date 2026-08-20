# SRX Public v0.1 Demo

The demo uses four versions of one evolving JSON configuration.

## Part A — Core CLI

```bash
bash demo/part_a_core_cli/run.sh
```

This creates one structural SRX record, reconstructs the target, verifies it, and prints record statistics.

Observed output from the release build is stored in `part_a_core_cli/OUTPUT.txt`.

## Part B — Temporal / Evidence Python API

```bash
python demo/part_b_temporal_api/run.py
```

This uses the real production SRX core through `make_production_core()`, ingests four snapshots, queries the history of `database.pool_size`, selectively reconstructs `v3/config.json`, and shows verified evidence.

Observed output from the release build is stored in `part_b_temporal_api/OUTPUT.txt`.
