#!/usr/bin/env bash
set -euo pipefail

export PATH="/Users/wangbin/anaconda3/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

APP_DIR="/Users/wangbin/Documents/Codex/codex-account-switcher"
PYTHON_BIN="${PYTHON_BIN:-/Users/wangbin/anaconda3/bin/python}"

cd "$APP_DIR"
mkdir -p "$APP_DIR/logs"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "python not found or not executable: $PYTHON_BIN" >&2
  exit 1
fi

exec "$PYTHON_BIN" -u app.py
