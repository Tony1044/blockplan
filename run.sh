#!/usr/bin/env bash
# Start Blockplan on macOS or Linux. The first run sets everything up.
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Blockplan needs Python 3.10 or newer. Install it from https://www.python.org and try again."
  exit 1
fi

if [ ! -d .venv ]; then
  echo "First run: setting up (this takes a minute)..."
  python3 -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -r requirements.txt
fi

[ -f .env ] || cp .env.example .env

PORT=$(grep -E '^PORT=' .env | cut -d= -f2 || true)
echo "Blockplan is starting. Open http://localhost:${PORT:-8080} in your browser."
echo "Press Ctrl+C to stop."
exec .venv/bin/python -m app.main
