#!/usr/bin/env bash
set -u

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$APP_DIR/logs"
LOG_FILE="$LOG_DIR/codex-keepalive.log"

mkdir -p "$LOG_DIR"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"
}

TMUX_BIN="${TMUX_BIN:-$(command -v tmux || true)}"
CODEX_BIN="${CODEX_BIN:-$(command -v codex || true)}"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"
CODEX_ACCOUNT_SEARCH_ROOT="${CODEX_ACCOUNT_SEARCH_ROOT:-/Users/wangbin}"
KEEPALIVE_STATE_FILE="${KEEPALIVE_STATE_FILE:-$APP_DIR/keepalive_state.json}"
KEEPALIVE_AUTO_WEEKLY_PAUSE="${KEEPALIVE_AUTO_WEEKLY_PAUSE:-0}"

if [[ -z "$TMUX_BIN" ]]; then
  log "tmux not found"
  exit 1
fi

if [[ -z "$CODEX_BIN" ]]; then
  log "codex not found"
  exit 1
fi

if [[ -z "$PYTHON_BIN" ]]; then
  log "python3 not found"
  exit 1
fi

should_keepalive() {
  local account_id="$1"
  "$PYTHON_BIN" - "$KEEPALIVE_STATE_FILE" "$account_id" "$KEEPALIVE_AUTO_WEEKLY_PAUSE" <<'PY'
import json
import sys
import time
from pathlib import Path

state_path = Path(sys.argv[1])
account_id = sys.argv[2]
auto_pause_enabled = sys.argv[3] in {"1", "true", "TRUE", "yes", "YES"}
try:
    state = json.loads(state_path.read_text(encoding="utf-8"))
except Exception:
    state = {}
entry = (state.get("accounts") if isinstance(state, dict) else {}) or {}
entry = entry.get(account_id) if isinstance(entry, dict) else {}
if not isinstance(entry, dict):
    entry = {}
mode = entry.get("mode", "auto")
pause_until = entry.get("auto_pause_until")
if mode == "off":
    sys.exit(1)
if auto_pause_enabled and mode == "auto" and isinstance(pause_until, (int, float)) and pause_until > time.time():
    sys.exit(1)
sys.exit(0)
PY
}

ensure_session() {
  local session_name="$1"
  local codex_home="$2"
  local auth_json="$codex_home/auth.json"

  if [[ ! -f "$auth_json" ]]; then
    log "skip $session_name: missing $auth_json"
    return 0
  fi

  if "$TMUX_BIN" has-session -t "$session_name" 2>/dev/null; then
    log "ok $session_name: already running"
    return 0
  fi

  log "start $session_name with CODEX_HOME=$codex_home"
  "$TMUX_BIN" new-session -d -s "$session_name" \
    "export CODEX_HOME='$codex_home'; exec '$CODEX_BIN'"
}

shopt -s nullglob
found_count=0
for codex_home in "$CODEX_ACCOUNT_SEARCH_ROOT"/.codex-*; do
  [[ -d "$codex_home" ]] || continue
  account_id="${codex_home##*/}"
  account_id="${account_id#.codex-}"
  if [[ -z "$account_id" ]]; then
    continue
  fi
  found_count=$((found_count + 1))
  if ! should_keepalive "$account_id"; then
    log "skip codex-$account_id: keepalive disabled or paused by policy"
    continue
  fi
  ensure_session "codex-$account_id" "$codex_home"
done
shopt -u nullglob

if [[ "$found_count" -eq 0 ]]; then
  log "no account directories found under $CODEX_ACCOUNT_SEARCH_ROOT"
fi

log "done"
