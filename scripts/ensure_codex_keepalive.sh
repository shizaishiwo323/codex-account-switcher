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
CODEX_TRUSTED_WORKDIR="${CODEX_TRUSTED_WORKDIR:-/Users/wangbin}"
KEEPALIVE_STATE_FILE="${KEEPALIVE_STATE_FILE:-$APP_DIR/keepalive_state.json}"
KEEPALIVE_PING_STATE_FILE="${KEEPALIVE_PING_STATE_FILE:-$APP_DIR/keepalive_ping_state.json}"
KEEPALIVE_STATUS_FILE="${KEEPALIVE_STATUS_FILE:-$APP_DIR/keepalive_status.json}"
KEEPALIVE_AUTO_WEEKLY_PAUSE="${KEEPALIVE_AUTO_WEEKLY_PAUSE:-0}"
KEEPALIVE_DAILY_PING_HOUR="${KEEPALIVE_DAILY_PING_HOUR:-0}"
KEEPALIVE_DAILY_PING_TEXT="${KEEPALIVE_DAILY_PING_TEXT:-你好}"

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

auth_is_usable() {
  local auth_json="$1"
  "$PYTHON_BIN" - "$auth_json" <<'PY'
import json
import sys
from pathlib import Path

try:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    sys.exit(1)
if not isinstance(data, dict):
    sys.exit(1)
tokens = data.get("tokens")
has_api_key = isinstance(data.get("OPENAI_API_KEY"), str) and bool(data["OPENAI_API_KEY"].strip())
has_tokens = (
    isinstance(tokens, dict)
    and isinstance(tokens.get("account_id"), str)
    and bool(tokens.get("account_id", "").strip())
    and any(isinstance(tokens.get(key), str) and bool(tokens.get(key, "").strip()) for key in ("access_token", "id_token", "refresh_token"))
)
sys.exit(0 if has_api_key or has_tokens else 1)
PY
}

ensure_trusted_project() {
  local codex_home="$1"
  local config_toml="$codex_home/config.toml"
  "$PYTHON_BIN" - "$config_toml" "$CODEX_TRUSTED_WORKDIR" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
project_dir = sys.argv[2]
header = f'[projects."{project_dir}"]'
path.parent.mkdir(parents=True, exist_ok=True)
try:
    text = path.read_text(encoding="utf-8")
except FileNotFoundError:
    text = ""

lines = text.splitlines()
out = []
in_section = False
found_section = False
section_had_trust = False
changed = False
section_re = re.compile(r"^\s*\[.*\]\s*$")

for line in lines:
    if line.strip() == header:
        in_section = True
        found_section = True
        section_had_trust = False
        out.append(line)
        continue
    if in_section and section_re.match(line):
        if not section_had_trust:
            out.append('trust_level = "trusted"')
            changed = True
        in_section = False
    if in_section and re.match(r"^\s*trust_level\s*=", line):
        if line.strip() != 'trust_level = "trusted"':
            out.append('trust_level = "trusted"')
            changed = True
        else:
            out.append(line)
        section_had_trust = True
        continue
    out.append(line)

if found_section and in_section and not section_had_trust:
    out.append('trust_level = "trusted"')
    changed = True
if not found_section:
    if out and out[-1].strip():
        out.append("")
    out.extend([header, 'trust_level = "trusted"'])
    changed = True

if changed:
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
PY
}

daily_ping_due() {
  local account_id="$1"
  "$PYTHON_BIN" - "$KEEPALIVE_PING_STATE_FILE" "$account_id" "$KEEPALIVE_DAILY_PING_HOUR" "${KEEPALIVE_NOW_EPOCH:-}" <<'PY'
import json
import os
import sys
import time
from pathlib import Path

state_path = Path(sys.argv[1])
account_id = sys.argv[2]
try:
    ping_hour = int(sys.argv[3])
except Exception:
    ping_hour = 0
now_arg = sys.argv[4]
now = float(now_arg) if now_arg else time.time()
local_time = time.localtime(now)
if local_time.tm_hour != ping_hour:
    sys.exit(1)
today = time.strftime("%Y-%m-%d", local_time)
try:
    state = json.loads(state_path.read_text(encoding="utf-8"))
except Exception:
    state = {}
if not isinstance(state, dict):
    state = {}
accounts = state.setdefault("accounts", {})
if not isinstance(accounts, dict):
    accounts = {}
    state["accounts"] = accounts
if accounts.get(account_id) == today:
    sys.exit(1)
accounts[account_id] = today
state_path.parent.mkdir(parents=True, exist_ok=True)
tmp_path = state_path.with_name(f".{state_path.name}.{os.getpid()}.tmp")
tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
tmp_path.replace(state_path)
sys.exit(0)
PY
}

maybe_send_daily_ping() {
  local session_name="$1"
  local account_id="$2"
  if ! "$TMUX_BIN" has-session -t "$session_name" 2>/dev/null; then
    return 0
  fi
  if daily_ping_due "$account_id"; then
    log "daily ping $session_name"
    if ! "$TMUX_BIN" send-keys -t "$session_name" "$KEEPALIVE_DAILY_PING_TEXT" Enter; then
      log "daily ping failed for $session_name"
    fi
  fi
}

update_session_status() {
  local session_name="$1"
  local account_id="$2"
  local pane_text
  if ! "$TMUX_BIN" has-session -t "$session_name" 2>/dev/null; then
    return 0
  fi
  pane_text="$("$TMUX_BIN" capture-pane -p -t "$session_name" -S -200 2>/dev/null || true)"
  "$PYTHON_BIN" - "$KEEPALIVE_STATUS_FILE" "$account_id" "$pane_text" <<'PY'
import json
import os
import sys
import time
from pathlib import Path

state_path = Path(sys.argv[1])
account_id = sys.argv[2]
pane_text = sys.argv[3]
try:
    state = json.loads(state_path.read_text(encoding="utf-8"))
except Exception:
    state = {}
if not isinstance(state, dict):
    state = {}
accounts = state.setdefault("accounts", {})
if not isinstance(accounts, dict):
    accounts = {}
    state["accounts"] = accounts

lower_text = pane_text.lower()
auth_invalid = (
    "access token could not be refreshed" in lower_text
    or "refresh token was already used" in lower_text
    or "please log out and sign in again" in lower_text
)
if auth_invalid:
    accounts[account_id] = {
        "status": "auth_invalid",
        "message": "后台 Codex 提示 refresh token 已失效，请重新登录这个账号。",
        "detail": "Your access token could not be refreshed because your refresh token was already used.",
        "updated_at": int(time.time()),
    }
elif account_id in accounts:
    accounts.pop(account_id, None)
else:
    sys.exit(0)

state_path.parent.mkdir(parents=True, exist_ok=True)
tmp_path = state_path.with_name(f".{state_path.name}.{os.getpid()}.tmp")
tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
tmp_path.replace(state_path)
PY
}

ensure_session() {
  local session_name="$1"
  local codex_home="$2"
  local auth_json="$codex_home/auth.json"

  if [[ ! -f "$auth_json" ]]; then
    log "skip $session_name: missing $auth_json"
    return 1
  fi

  if ! auth_is_usable "$auth_json"; then
    log "skip $session_name: invalid or expired-looking auth.json"
    return 1
  fi

  ensure_trusted_project "$codex_home"

  if "$TMUX_BIN" has-session -t "$session_name" 2>/dev/null; then
    log "ok $session_name: already running"
    return 0
  fi

  log "start $session_name with CODEX_HOME=$codex_home"
  "$TMUX_BIN" new-session -d -s "$session_name" \
    "export CODEX_HOME='$codex_home'; exec '$CODEX_BIN' --cd '$CODEX_TRUSTED_WORKDIR'"
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
  if ensure_session "codex-$account_id" "$codex_home"; then
    maybe_send_daily_ping "codex-$account_id" "$account_id"
    update_session_status "codex-$account_id" "$account_id"
  fi
done
shopt -u nullglob

if [[ "$found_count" -eq 0 ]]; then
  log "no account directories found under $CODEX_ACCOUNT_SEARCH_ROOT"
fi

log "done"
