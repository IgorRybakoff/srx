"""
GitRepoConnector — v0.1 priority connector #2.

Basic, local-repository-only connector. Uses the system `git` binary
via subprocess against a local repository path (no network access).
Each commit is treated as a version, in commit order (oldest first),
restricted to a given branch/ref.

This is intentionally minimal for v0.1: no rename detection beyond
what `git diff` reports is not consumed here (list_files/read_file are
snapshot-based, not diff-based — diffing across versions is the
temporal layer's job, not the connector's).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..errors import VersionNotFound


class GitRepoConnector:
    def __init__(self, repo_path: str | Path, ref: str = "HEAD"):
        self.repo_path = Path(repo_path)
        self.ref = ref
        self._commits: list[str] | None = None

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo_path), *args],
            capture_output=True, text=True, check=True,
        )
        return result.stdout

    def list_versions(self) -> list[str]:
        if self._commits is None:
            out = self._run("log", "--reverse", "--pretty=format:%H", self.ref)
            self._commits = [line for line in out.splitlines() if line]
        return list(self._commits)

    def _check_known(self, version_id: str) -> None:
        if version_id not in self.list_versions():
            raise VersionNotFound(version_id)

    def list_files(self, version_id: str) -> list[str]:
        self._check_known(version_id)
        out = self._run("ls-tree", "-r", "--name-only", version_id)
        return [line for line in out.splitlines() if line]

    def read_file(self, version_id: str, path: str) -> bytes:
        self._check_known(version_id)
        result = subprocess.run(
            ["git", "-C", str(self.repo_path), "show", f"{version_id}:{path}"],
            capture_output=True, check=True,
        )
        return result.stdout

    def version_timestamp(self, version_id: str) -> str:
        self._check_known(version_id)
        out = self._run("show", "-s", "--format=%cI", version_id)
        return out.strip()
