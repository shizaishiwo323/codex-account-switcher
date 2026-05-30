from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


MODE_AUTO = "auto"
MODE_ON = "on"
MODE_OFF = "off"
VALID_MODES = {MODE_AUTO, MODE_ON, MODE_OFF}


def tmux_session_name(account_id: str) -> str:
    return f"codex-{account_id}"


def weekly_window(account: dict[str, Any]) -> dict[str, Any] | None:
    usage = account.get("usage") if isinstance(account.get("usage"), dict) else {}
    for key in ("primary", "secondary"):
        window = usage.get(key)
        if isinstance(window, dict) and window.get("label") == "1周":
            return window
    return None


def update_auto_pause_from_usage(
    state: dict[str, Any],
    account: dict[str, Any],
    now: float | None = None,
) -> bool:
    current_time = time.time() if now is None else now
    window = weekly_window(account)
    if not window:
        return False

    remaining = window.get("remaining_percent")
    reset_at = window.get("reset_at")
    if isinstance(remaining, (int, float)) and remaining <= 0 and isinstance(reset_at, (int, float)) and reset_at > current_time:
        changed = state.get("auto_pause_until") != reset_at
        state["auto_pause_until"] = reset_at
        return changed

    if "auto_pause_until" in state:
        state.pop("auto_pause_until", None)
        return True
    return False


def account_keepalive_payload(
    account: dict[str, Any],
    state: dict[str, Any],
    running: bool,
    now: float | None = None,
    auto_pause_enabled: bool = True,
) -> dict[str, Any]:
    current_time = time.time() if now is None else now
    mode = state.get("mode")
    if mode not in VALID_MODES:
        mode = MODE_AUTO

    window = weekly_window(account)
    weekly_remaining = window.get("remaining_percent") if isinstance(window, dict) else None
    weekly_reset_at = window.get("reset_at") if isinstance(window, dict) else None
    pause_until = state.get("auto_pause_until")

    desired = True
    reason = "auto"
    resume_at = None
    if mode == MODE_OFF:
        desired = False
        reason = "manual_off"
    elif mode == MODE_ON:
        desired = True
        reason = "manual_on"
    elif auto_pause_enabled and isinstance(pause_until, (int, float)) and pause_until > current_time:
        desired = False
        reason = "weekly_exhausted"
        resume_at = pause_until

    return {
        "enabled": bool(account.get("can_switch")),
        "mode": mode,
        "running": running,
        "desired": desired,
        "reason": reason,
        "session": tmux_session_name(str(account.get("id") or "")),
        "weekly_remaining_percent": weekly_remaining,
        "weekly_reset_at": weekly_reset_at,
        "resume_at": resume_at,
    }


class KeepaliveState:
    def __init__(self, path: Path, auto_pause_enabled: bool = True) -> None:
        self.path = path
        self.auto_pause_enabled = auto_pause_enabled

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "accounts": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"version": 1, "accounts": {}}
        if not isinstance(data, dict):
            return {"version": 1, "accounts": {}}
        accounts = data.get("accounts")
        if not isinstance(accounts, dict):
            accounts = {}
        return {"version": 1, "accounts": accounts}

    def save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "accounts": state.get("accounts") if isinstance(state.get("accounts"), dict) else {},
        }
        with tempfile.NamedTemporaryFile(
            "w",
            delete=False,
            dir=str(self.path.parent),
            prefix=".keepalive-state-",
            suffix=".json",
            encoding="utf-8",
        ) as tmp:
            tmp_path = Path(tmp.name)
            json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp_path.replace(self.path)

    def account_state(self, state: dict[str, Any], account_id: str) -> dict[str, Any]:
        accounts = state.setdefault("accounts", {})
        if not isinstance(accounts, dict):
            accounts = {}
            state["accounts"] = accounts
        entry = accounts.setdefault(account_id, {})
        if not isinstance(entry, dict):
            entry = {}
            accounts[account_id] = entry
        if entry.get("mode") not in VALID_MODES:
            entry["mode"] = MODE_AUTO
        return entry

    def update_mode(self, account_id: str, mode: str) -> dict[str, Any]:
        if mode not in VALID_MODES:
            raise ValueError("保活模式必须是 auto、on 或 off")
        state = self.load()
        entry = self.account_state(state, account_id)
        entry["mode"] = mode
        self.save(state)
        return entry

    def update_auto_pauses(self, accounts: list[dict[str, Any]]) -> None:
        state = self.load()
        if not self.auto_pause_enabled:
            if self.clear_auto_pauses(state):
                self.save(state)
            return
        changed = False
        now = time.time()
        for account in accounts:
            account_id = account.get("id")
            if not account.get("can_switch") or not isinstance(account_id, str):
                continue
            entry = self.account_state(state, account_id)
            changed = update_auto_pause_from_usage(entry, account, now=now) or changed
        if changed:
            self.save(state)

    def clear_auto_pauses(self, state: dict[str, Any]) -> bool:
        accounts = state.get("accounts")
        if not isinstance(accounts, dict):
            return False
        changed = False
        for entry in accounts.values():
            if isinstance(entry, dict) and "auto_pause_until" in entry:
                entry.pop("auto_pause_until", None)
                changed = True
        return changed

    def attach_payloads(self, accounts: list[dict[str, Any]], running_sessions: set[str] | None = None) -> None:
        state = self.load()
        sessions = running_sessions if running_sessions is not None else tmux_sessions()
        now = time.time()
        for account in accounts:
            account_id = account.get("id")
            if not account.get("can_switch") or not isinstance(account_id, str):
                account["keepalive"] = {"enabled": False}
                continue
            entry = self.account_state(state, account_id)
            account["keepalive"] = account_keepalive_payload(
                account,
                entry,
                running=tmux_session_name(account_id) in sessions,
                now=now,
                auto_pause_enabled=self.auto_pause_enabled,
            )

    def stop_paused_auto_sessions(self, accounts: list[dict[str, Any]]) -> bool:
        changed = False
        for account in accounts:
            account_id = account.get("id")
            keepalive = account.get("keepalive")
            if not isinstance(account_id, str) or not isinstance(keepalive, dict):
                continue
            if keepalive.get("mode") == MODE_AUTO and keepalive.get("running") and not keepalive.get("desired"):
                stop_keepalive_session(account_id)
                changed = True
        return changed


def tmux_sessions() -> set[str]:
    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def start_keepalive_session(account: dict[str, Any]) -> None:
    account_id = str(account["id"])
    codex_home = str(Path(account["auth_path"]).expanduser().resolve().parent)
    session = tmux_session_name(account_id)
    if session in tmux_sessions():
        return
    subprocess.run(
        [
            "tmux",
            "new-session",
            "-d",
            "-s",
            session,
            f"export CODEX_HOME='{codex_home}'; exec codex",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def stop_keepalive_session(account_id: str) -> None:
    session = tmux_session_name(account_id)
    if session not in tmux_sessions():
        return
    subprocess.run(
        ["tmux", "kill-session", "-t", session],
        check=True,
        capture_output=True,
        text=True,
    )
