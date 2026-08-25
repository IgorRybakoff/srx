#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WORK_DIR="${SCRIPT_DIR}/.vite50_work"
VITE_REPO="${WORK_DIR}/vite"
SRX_WORK="${WORK_DIR}/srx"

cd "${REPO_ROOT}"
rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}"

# Pinned public project/release so the demo does not drift with Vite HEAD.
echo "Cloning Vite v7.1.0 real history (depth 60)..."
git clone --quiet --depth 60 --branch v7.1.0 --single-branch \
  https://github.com/vitejs/vite.git "${VITE_REPO}"

echo "Running SRX over 50 first-parent commits..."
python demo/real_history/run.py \
  --repo "${VITE_REPO}" \
  --limit 50 \
  --work-dir "${SRX_WORK}" \
  --track README.md \
  --track packages/vite/package.json \
  --json-file packages/vite/package.json
