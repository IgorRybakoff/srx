"""Real-history SRX demo against an actual local Git repository.

The demo ingests a bounded first-parent slice of real Git history through the
existing GitRepoConnector + SRX temporal engine. It does not generate synthetic
snapshots. After persistence reload it:

1. shows verified file history for a tracked real file,
2. discovers one changing nested JSON key when a JSON file is available,
3. reconstructs one historical file exactly and compares it to `git show`.

Examples:
    python demo/real_history/run.py --repo . --limit 50
    python demo/real_history/run.py --repo /path/to/vite --limit 50 \
        --track README.md --track packages/vite/package.json \
        --json-file packages/vite/package.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from srx_temporal.cas import ContentAddressableStore
from srx_temporal.connectors.git_repo import GitRepoConnector
from srx_temporal.core_adapter import make_production_core
from srx_temporal.ingest import ingest_snapshot
from srx_temporal.persistence import load_index, save_index
from srx_temporal.reconstructor import SelectiveReconstructor
from srx_temporal.temporal_index import TemporalIndex


class FilteredGitConnector:
    """Read-only path filter over the existing GitRepoConnector."""

    def __init__(self, base: GitRepoConnector, allowed_paths: set[str]):
        self.base = base
        self.allowed_paths = set(allowed_paths)

    def list_versions(self) -> list[str]:
        return self.base.list_versions()

    def list_files(self, version_id: str) -> list[str]:
        return [
            path
            for path in self.base.list_files(version_id)
            if path in self.allowed_paths
        ]

    def read_file(self, version_id: str, path: str) -> bytes:
        return self.base.read_file(version_id, path)

    def version_timestamp(self, version_id: str) -> str:
        return self.base.version_timestamp(version_id)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _first_parent_commits(repo: Path, limit: int) -> tuple[int, list[str]]:
    raw = _git(repo, "rev-list", "--first-parent", "--reverse", "HEAD")
    all_commits = [line for line in raw.splitlines() if line]
    if len(all_commits) < 2:
        raise RuntimeError("real-history demo requires at least two Git commits")
    return len(all_commits), all_commits[-limit:]


def _commit_subject(repo: Path, commit: str) -> str:
    return _git(repo, "show", "-s", "--format=%s", commit)


def _flatten_json(value, prefix: str = "") -> dict[str, str]:
    """Return deterministic leaf key -> canonical JSON value strings."""
    if isinstance(value, dict):
        out: dict[str, str] = {}
        for key in sorted(value):
            path = str(key) if not prefix else f"{prefix}.{key}"
            out.update(_flatten_json(value[key], path))
        return out
    return {
        prefix: json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    }


def _discover_json_key(
    base: GitRepoConnector,
    commits: list[str],
    candidate_paths: list[str] | None = None,
    max_candidates: int = 8,
) -> tuple[str, str, int] | None:
    """Find a real JSON file/key with the most value transitions."""
    path_counts: Counter[str] = Counter()
    files_by_commit: dict[str, set[str]] = {}

    for commit in commits:
        files = set(base.list_files(commit))
        files_by_commit[commit] = files
        for path in files:
            if path.endswith(".json"):
                path_counts[path] += 1

    if candidate_paths:
        candidates = [
            path
            for path in candidate_paths
            if any(path in files for files in files_by_commit.values())
        ]
    else:
        candidates = [path for path, _ in path_counts.most_common(max_candidates)]

    best: tuple[str, str, int] | None = None

    for path in candidates:
        previous: dict[str, str] | None = None
        counts: Counter[str] = Counter()
        seen_keys: set[str] = set()

        for commit in commits:
            if path not in files_by_commit[commit]:
                current: dict[str, str] = {}
            else:
                raw = base.read_file(commit, path)
                if len(raw) > 250_000:
                    continue
                try:
                    value = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if not isinstance(value, dict):
                    continue
                current = _flatten_json(value)

            if previous is not None:
                for key in set(previous) | set(current):
                    if previous.get(key) != current.get(key):
                        counts[key] += 1
            previous = current
            seen_keys.update(current)

        for key in seen_keys:
            changes = counts[key]
            if changes <= 0:
                continue
            candidate = (path, key, changes)
            if best is None or candidate[2] > best[2]:
                best = candidate

    return best


def _path_exists_in_slice(base: GitRepoConnector, commits: list[str], path: str) -> bool:
    return any(path in set(base.list_files(commit)) for commit in commits)


def _choose_reconstruct_target(index: TemporalIndex, preferred_path: str) -> tuple[str, str]:
    for manifest in index.list_versions():
        if any(entry.path == preferred_path for entry in manifest.files):
            return manifest.version_id, preferred_path
    for manifest in index.list_versions():
        if manifest.files:
            return manifest.version_id, manifest.files[0].path
    raise RuntimeError("no tracked file available for reconstruction")


def main() -> int:
    parser = argparse.ArgumentParser(description="SRX real Git history demo")
    parser.add_argument("--repo", default=".", help="Local Git repository path")
    parser.add_argument("--limit", type=int, default=50, help="Max first-parent commits to ingest")
    parser.add_argument(
        "--track",
        action="append",
        default=[],
        help="Track only this path (repeatable). Defaults to README/ROADMAP/pyproject when present.",
    )
    parser.add_argument(
        "--json-file",
        default=None,
        help="Restrict nested-key discovery to this JSON file.",
    )
    parser.add_argument(
        "--work-dir",
        default="demo/.real_history_work",
        help="Disposable demo work directory",
    )
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        raise SystemExit(f"not a local Git repository: {repo}")
    if args.limit < 2:
        raise SystemExit("--limit must be >= 2")

    total_commits, commits = _first_parent_commits(repo, args.limit)
    base = GitRepoConnector(repo)

    json_candidates = [args.json_file] if args.json_file else None
    json_choice = _discover_json_key(base, commits, candidate_paths=json_candidates)

    requested_paths = args.track or ["README.md", "ROADMAP.md", "pyproject.toml"]
    allowed_paths = {
        path for path in requested_paths if _path_exists_in_slice(base, commits, path)
    }
    if args.json_file and _path_exists_in_slice(base, commits, args.json_file):
        allowed_paths.add(args.json_file)
    elif json_choice is not None:
        allowed_paths.add(json_choice[0])

    if not allowed_paths:
        newest_files = base.list_files(commits[-1])
        if not newest_files:
            raise SystemExit("selected Git history contains no files")
        allowed_paths.add(newest_files[0])

    connector = FilteredGitConnector(base, allowed_paths)
    work_dir = Path(args.work_dir).resolve()
    store = work_dir / "store"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    store.mkdir(parents=True, exist_ok=True)

    cas = ContentAddressableStore(store / "cas")
    index = TemporalIndex(cas)
    core = make_production_core()

    previous: str | None = None
    for commit in commits:
        parents = (previous,) if previous is not None else ()
        ingest_snapshot(
            index=index,
            cas=cas,
            connector=connector,
            version_id=commit,
            parent_ids=parents,
            message=_commit_subject(repo, commit),
            core=core,
        )
        previous = commit

    save_index(index, store)
    del index

    loaded = load_index(store)
    reconstructor = SelectiveReconstructor(loaded, loaded.cas, core)

    versions = loaded.list_versions()
    print("=== SRX Real Git History Demo ===")
    print(f"Repository: {repo}")
    print(f"First-parent commits available: {total_commits}")
    print(f"Imported real commits: {len(versions)}")
    print(f"Tracked paths: {', '.join(sorted(allowed_paths))}")
    print(f"Persistence reload: PASS ({len(versions)} versions)")
    print()

    preferred_timeline = next(
        (path for path in requested_paths if path in allowed_paths),
        sorted(allowed_paths)[0],
    )
    file_path = preferred_timeline
    file_hits = loaded.timeline_by_file(file_path)
    verified_file_hits = sum(hit.evidence.verification_passed for hit in file_hits)
    print(f"File timeline: {file_path}")
    print(f"  change events: {len(file_hits)}")
    print(f"  verified evidence: {verified_file_hits}/{len(file_hits)}")
    for hit in file_hits[-8:]:
        print(
            f"  {hit.version_id[:10]}  {hit.timestamp}  {hit.change_type}  "
            f"verify={'PASS' if hit.evidence.verification_passed else 'FAIL'}"
        )
    print()

    key_hits = []
    verified_key_hits = 0
    if json_choice is not None:
        json_path, key_path, observed_transitions = json_choice
        key_hits = loaded.timeline_by_key(key_path, file_path=json_path)
        verified_key_hits = sum(hit.evidence.verification_passed for hit in key_hits)
        print("Nested-key timeline discovered from real history:")
        print(f"  file: {json_path}")
        print(f"  key: {key_path}")
        print(f"  observed value transitions during discovery: {observed_transitions}")
        print(f"  temporal hits: {len(key_hits)}")
        print(f"  verified evidence: {verified_key_hits}/{len(key_hits)}")
        for hit in key_hits[-8:]:
            print(
                f"  {hit.version_id[:10]}  {hit.change_type}  "
                f"{hit.evidence.previous_value_ref} -> {hit.evidence.current_value_ref}  "
                f"verify={'PASS' if hit.evidence.verification_passed else 'FAIL'}"
            )
        print()
    else:
        print("Nested-key timeline: no changing JSON leaf found in selected history slice")
        print()

    version_id, reconstruct_path = _choose_reconstruct_target(loaded, file_path)
    result = reconstructor.reconstruct_file(version_id, reconstruct_path)
    original = base.read_file(version_id, reconstruct_path)
    original_sha = hashlib.sha256(original).hexdigest()

    print("Historical reconstruction:")
    print(f"  commit: {version_id}")
    print(f"  file: {reconstruct_path}")
    print(f"  reconstructed bytes: {len(result.bytes_data)}")
    print(f"  SHA-256: {result.sha256}")
    print(f"  SRX verification: {'PASS' if result.verification_passed else 'FAIL'}")
    print(f"  bit-perfect vs git show: {'PASS' if result.bytes_data == original else 'FAIL'}")
    print(f"  source SHA match: {'PASS' if result.sha256 == original_sha else 'FAIL'}")

    if not result.verification_passed or result.bytes_data != original or result.sha256 != original_sha:
        return 1
    if file_hits and verified_file_hits != len(file_hits):
        return 1
    if key_hits and verified_key_hits != len(key_hits):
        return 1

    print()
    print("=== Real-history demo complete ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
