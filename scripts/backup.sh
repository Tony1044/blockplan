#!/usr/bin/env bash
# Make a dated copy of all maps:  bash scripts/backup.sh
# Safe to run while Blockplan is running.
set -euo pipefail
cd "$(dirname "$0")/.."
DATA_DIR=$(grep -E '^DATA_DIR=' .env 2>/dev/null | cut -d= -f2 || true)
DB="${DATA_DIR:-./data}/blockplan.db"
mkdir -p backups
OUT="backups/blockplan-$(date +%Y-%m-%d-%H%M).db"
python3 -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()" "$DB" "$OUT"
echo "Saved $OUT"
