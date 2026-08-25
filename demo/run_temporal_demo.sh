#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORK_DIR="${SCRIPT_DIR}/.temporal_demo_work"
STORE="${WORK_DIR}/store"
SNAPSHOTS="${WORK_DIR}/snapshots"
RESTORED="${WORK_DIR}/restored_v3.json"

cd "${REPO_ROOT}"
rm -rf "${WORK_DIR}"
mkdir -p "${SNAPSHOTS}/v1" "${SNAPSHOTS}/v2" "${SNAPSHOTS}/v3" "${SNAPSHOTS}/v4"

if command -v srx >/dev/null 2>&1; then
  SRX=(srx)
else
  SRX=(python3 -m srx.cli.main)
fi

cat > "${SNAPSHOTS}/v1/config.json" <<'EOF'
{
  "app": {"name": "myservice", "version": "1.0.0"},
  "database": {
    "driver": "sqlite",
    "pool_size": 4,
    "url": "sqlite:///data.db"
  }
}
EOF

cat > "${SNAPSHOTS}/v2/config.json" <<'EOF'
{
  "app": {"name": "myservice", "version": "1.0.0"},
  "database": {
    "driver": "sqlite",
    "pool_size": 16,
    "url": "sqlite:///data.db"
  }
}
EOF

cat > "${SNAPSHOTS}/v3/config.json" <<'EOF'
{
  "app": {"name": "myservice", "version": "1.0.0"},
  "database": {
    "driver": "postgres",
    "pool_size": 16,
    "url": "postgres://localhost/mydb"
  }
}
EOF

cat > "${SNAPSHOTS}/v4/config.json" <<'EOF'
{
  "app": {"name": "myservice", "version": "1.0.0"},
  "database": {
    "driver": "postgres",
    "pool_size": 32,
    "url": "postgres://localhost/mydb"
  },
  "cache": {
    "driver": "redis",
    "ttl": 3600
  }
}
EOF

echo "=== SRX Temporal CLI Demo ==="
echo

echo "[1/7] Initializing store..."
"${SRX[@]}" temporal init "${STORE}"
echo

echo "[2/7] Adding versions..."
"${SRX[@]}" temporal add "${STORE}" "${SNAPSHOTS}/v1" -m "initial config"
"${SRX[@]}" temporal add "${STORE}" "${SNAPSHOTS}/v2" -m "tune pool size"
"${SRX[@]}" temporal add "${STORE}" "${SNAPSHOTS}/v3" -m "switch to postgres"
"${SRX[@]}" temporal add "${STORE}" "${SNAPSHOTS}/v4" -m "add cache, tune pool"
echo

echo "[3/7] Listing versions..."
"${SRX[@]}" temporal list "${STORE}"
echo

echo "[4/7] Querying timeline for database.pool_size..."
"${SRX[@]}" temporal timeline "${STORE}" --key "database.pool_size" --file "config.json"
echo

echo "[5/7] Resolving verified evidence..."
"${SRX[@]}" temporal evidence "${STORE}" --key "database.pool_size" --file "config.json"
echo

echo "[6/7] Selectively reconstructing v3/config.json..."
"${SRX[@]}" temporal reconstruct "${STORE}" v3 --file "config.json" -o "${RESTORED}"
echo

echo "[7/7] Verifying restored bytes against the original v3 file..."
if cmp -s "${RESTORED}" "${SNAPSHOTS}/v3/config.json"; then
  echo "Bit-perfect comparison: PASS"
else
  echo "Bit-perfect comparison: FAIL" >&2
  exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
  RESTORED_SHA="$(sha256sum "${RESTORED}" | awk '{print $1}')"
elif command -v shasum >/dev/null 2>&1; then
  RESTORED_SHA="$(shasum -a 256 "${RESTORED}" | awk '{print $1}')"
else
  RESTORED_SHA="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "${RESTORED}")"
fi

echo "Restored file SHA-256: ${RESTORED_SHA}"
echo
echo "=== Demo complete ==="
