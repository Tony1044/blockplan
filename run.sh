#!/usr/bin/env bash
# Start Blockplan on macOS or Linux. The first run sets everything up.
set -euo pipefail
cd "$(dirname "$0")"

# Find Python 3.10 or newer. macOS's built-in python3 is often 3.9, so try newer names first.
PY=""
for c in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Blockplan needs Python 3.10 or newer."
  if command -v python3 >/dev/null 2>&1; then echo "This computer has $(python3 --version 2>&1), which is too old."; fi
  if [ "$(uname)" = "Darwin" ]; then
    echo "On a Mac, install it from https://www.python.org/downloads/macos/ or run: brew install python"
  else
    echo "Install it with your package manager (for example: sudo apt install python3 python3-venv) or from https://www.python.org"
  fi
  exit 1
fi

# A setup made with an older Python is replaced.
if [ -d .venv ] && ! .venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
  rm -rf .venv
fi

if [ ! -d .venv ]; then
  echo "First run: setting up with $($PY --version) (this takes a minute)..."
  "$PY" -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -r requirements.txt
  cp requirements.txt .venv/.requirements
fi

# After an update, install anything new.
if ! cmp -s requirements.txt .venv/.requirements; then
  echo "Installing updates..."
  .venv/bin/pip install --quiet -r requirements.txt
  cp requirements.txt .venv/.requirements
fi

[ -f .env ] || cp .env.example .env

echo "Blockplan is starting. Press Ctrl+C to stop."
exec .venv/bin/python -m app.main
