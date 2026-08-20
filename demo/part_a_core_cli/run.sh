#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
WORK=".demo_work"
rm -rf "$WORK"
mkdir -p "$WORK"
trap 'rm -rf "$WORK"' EXIT

V1="snapshots/v1/config.json"
V2="snapshots/v2/config.json"
RECORD="$WORK/v1_v2.srx"
RESTORED="$WORK/restored_v2.json"

echo "=== SRX Core CLI demo ==="
echo

echo "--- structural diff v1 -> v2 ---"
srx diff "$V1" "$V2" -o "$RECORD"
echo

echo "--- reconstruct v2 ---"
srx reconstruct "$RECORD" --ref "$V1" -o "$RESTORED"
echo

echo "--- verify ---"
srx verify "$RECORD" --ref "$V1"
echo

echo "--- record stats ---"
srx stats "$RECORD"
echo

echo "--- byte equality ---"
cmp -s "$V2" "$RESTORED"
echo "PASS: restored_v2.json is byte-for-byte identical to v2/config.json"
