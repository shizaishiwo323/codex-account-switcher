#!/usr/bin/env bash
set -u

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

LOG_DIR="/Users/wangbin/Documents/Codex/任意任务/codex-account-switcher/logs"
LOG_FILE="$LOG_DIR/codex-keepalive.log"

mkdir -p "$LOG_DIR"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"
}

TMUX_BIN="${TMUX_BIN:-$(command -v tmux || true)}"
CODEX_BIN="${CODEX_BIN:-$(command -v codex || true)}"

if [[ -z "$TMUX_BIN" ]]; then
  log "tmux not found"
  exit 1
fi

if [[ -z "$CODEX_BIN" ]]; then
  log "codex not found"
  exit 1
fi

ACCOUNTS=(
  "codex-shizaishiwo0|/Users/wangbin/.codex-shizaishiwo0"
  "codex-shizaishiwo123|/Users/wangbin/.codex-shizaishiwo123"
  "codex-shizaishiwo323|/Users/wangbin/.codex-shizaishiwo323"
)

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

for item in "${ACCOUNTS[@]}"; do
  session_name="${item%%|*}"
  codex_home="${item#*|}"
  ensure_session "$session_name" "$codex_home"
done

log "done"
