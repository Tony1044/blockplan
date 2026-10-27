#!/usr/bin/env bash
# Install Blockplan as a service on a Linux server so it starts on boot.
# Run from the blockplan folder:  bash deploy/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."
APP_DIR="$(pwd)"

echo "Setting up Blockplan in $APP_DIR"
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt
[ -f .env ] || { cp .env.example .env; echo "Created .env – add your ANTHROPIC_API_KEY to it."; }
mkdir -p data

mkdir -p "$HOME/.config/systemd/user"
sed "s#@APP_DIR@#$APP_DIR#g" deploy/blockplan.service > "$HOME/.config/systemd/user/blockplan.service"
systemctl --user daemon-reload
systemctl --user enable --now blockplan
# Keep running after you log out.
loginctl enable-linger "$USER" 2>/dev/null || sudo loginctl enable-linger "$USER" || true

PORT=$(grep -E '^PORT=' .env | cut -d= -f2 || true)
echo
echo "Blockplan is running on port ${PORT:-8080}."
echo "Status:  systemctl --user status blockplan"
echo "Logs:    journalctl --user -u blockplan -f"
echo "Restart after changing .env:  systemctl --user restart blockplan"
