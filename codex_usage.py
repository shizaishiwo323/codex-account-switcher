from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
CODEX_OAUTH_TOKEN_URL = "https://auth.openai.com/oauth/token"
DEFAULT_HTTP_TIMEOUT = 20.0


@dataclass
class CodexAuth:
    auth_path: Path
    access_token: str
    refresh_token: str | None
    id_token: str | None
    account_id: str | None
    base_url: str
    last_refresh: str | None
    source_format: str


def _b64url_json(segment: str) -> dict[str, Any]:
    padding = "=" * (-len(segment) % 4)
    raw = base64.urlsafe_b64decode(segment + padding)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JWT payload is not a JSON object")
    return data


def decode_jwt_payload(token: str | None) -> dict[str, Any]:
    if not token or token.count(".") < 2:
        return {}
    try:
        return _b64url_json(token.split(".")[1])
    except Exception:
        return {}


def jwt_expires_soon(token: str | None, skew_seconds: int = 120) -> bool:
    payload = decode_jwt_payload(token)
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        return False
    return time.time() + skew_seconds >= float(exp)


def token_account_id(token: str | None) -> str | None:
    payload = decode_jwt_payload(token)
    auth = payload.get("https://api.openai.com/auth")
    if isinstance(auth, dict):
        value = auth.get("chatgpt_account_id")
        if isinstance(value, str) and value:
            return value
    return None


def token_text_field(token: str | None, field: str) -> str | None:
    payload = decode_jwt_payload(token)
    value = payload.get(field)
    if isinstance(value, str) and value:
        return value
    return None


def load_auth(path: Path) -> CodexAuth:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("auth.json root must be an object")

    tokens = data.get("tokens")
    if isinstance(tokens, dict):
        access_token = tokens.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("Codex auth file is missing tokens.access_token")
        refresh_token = tokens.get("refresh_token")
        id_token = tokens.get("id_token")
        account_id = tokens.get("account_id") or token_account_id(access_token)
        return CodexAuth(
            auth_path=path,
            access_token=access_token,
            refresh_token=refresh_token if isinstance(refresh_token, str) else None,
            id_token=id_token if isinstance(id_token, str) else None,
            account_id=account_id if isinstance(account_id, str) else None,
            base_url=DEFAULT_CODEX_BASE_URL,
            last_refresh=data.get("last_refresh") if isinstance(data.get("last_refresh"), str) else None,
            source_format="codex",
        )

    pool = data.get("credential_pool")
    if isinstance(pool, dict):
        entries = pool.get("openai-codex")
        if isinstance(entries, list) and entries and isinstance(entries[0], dict):
            entry = entries[0]
            access_token = entry.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise ValueError("Hermes auth file is missing credential_pool.openai-codex[0].access_token")
            refresh_token = entry.get("refresh_token")
            base_url = entry.get("base_url")
            return CodexAuth(
                auth_path=path,
                access_token=access_token,
                refresh_token=refresh_token if isinstance(refresh_token, str) else None,
                id_token=None,
                account_id=token_account_id(access_token),
                base_url=base_url.rstrip("/") if isinstance(base_url, str) and base_url else DEFAULT_CODEX_BASE_URL,
                last_refresh=entry.get("last_refresh") if isinstance(entry.get("last_refresh"), str) else None,
                source_format="hermes",
            )

    raise ValueError("Unsupported auth.json format: expected Codex tokens or Hermes credential_pool")


def refresh_access_token(auth: CodexAuth, timeout: float = DEFAULT_HTTP_TIMEOUT) -> str:
    if not auth.refresh_token:
        raise RuntimeError("access token is expired and refresh_token is missing")
    codex_oauth_client_id = "app_EMoamEEZ73f0CkXaXp7hrann"
    form = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": auth.refresh_token,
            "client_id": codex_oauth_client_id,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        CODEX_OAUTH_TOKEN_URL,
        data=form,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "codex-account-switcher/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError("refresh response did not contain access_token")
    return access_token


def request_json(url: str, access_token: str, timeout: float = DEFAULT_HTTP_TIMEOUT) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Origin": "https://chatgpt.com",
            "User-Agent": "codex-cli/0.128.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read(500).decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return payload


def window_label(seconds: Any) -> str:
    if not isinstance(seconds, (int, float)):
        return "-"
    seconds = int(seconds)
    if seconds % 604800 == 0:
        return f"{seconds // 604800}周"
    if seconds % 86400 == 0:
        return f"{seconds // 86400}天"
    if seconds % 3600 == 0:
        return f"{seconds // 3600}小时"
    return f"{max(1, seconds // 60)}分钟"


def reset_time(epoch: Any, show_date: bool) -> str:
    if not isinstance(epoch, (int, float)):
        return "-"
    reset_at = datetime.fromtimestamp(float(epoch)).astimezone()
    if show_date:
        return f"{reset_at.month}月{reset_at.day}日"
    return reset_at.strftime("%H:%M")


def remaining_percent(window: Any) -> int | None:
    if not isinstance(window, dict):
        return None
    used = window.get("used_percent")
    if not isinstance(used, (int, float)):
        return None
    return round(max(0, min(100, 100 - float(used))))


def window_reset_shows_date(window: dict[str, Any]) -> bool:
    seconds = window.get("limit_window_seconds")
    return isinstance(seconds, (int, float)) and seconds >= 86400


def format_window(window: Any) -> dict[str, Any]:
    if not isinstance(window, dict):
        return {"label": "-", "remaining_percent": None, "reset": "-"}
    return {
        "label": window_label(window.get("limit_window_seconds")),
        "remaining_percent": remaining_percent(window),
        "reset": reset_time(window.get("reset_at"), window_reset_shows_date(window)),
        "used_percent": window.get("used_percent"),
        "reset_at": window.get("reset_at"),
    }


def query_usage(auth_path: Path, timeout: float = DEFAULT_HTTP_TIMEOUT) -> dict[str, Any]:
    auth = load_auth(auth_path.expanduser().resolve())
    access_token = auth.access_token
    refreshed = False
    if jwt_expires_soon(access_token):
        access_token = refresh_access_token(auth, timeout)
        refreshed = True
        auth.account_id = auth.account_id or token_account_id(access_token)

    usage = request_json(f"{auth.base_url.rstrip('/')}/usage", access_token, timeout)
    rate_limit = usage.get("rate_limit") if isinstance(usage.get("rate_limit"), dict) else {}
    email = token_text_field(auth.id_token, "email")
    name = token_text_field(auth.id_token, "name")

    return {
        "path": str(auth.auth_path),
        "format": auth.source_format,
        "email": email,
        "name": name,
        "account_id": auth.account_id,
        "usage_account_id": usage.get("account_id"),
        "plan": usage.get("plan_type"),
        "token_refreshed": refreshed,
        "allowed": rate_limit.get("allowed"),
        "limit_reached": rate_limit.get("limit_reached"),
        "primary": format_window(rate_limit.get("primary_window")),
        "secondary": format_window(rate_limit.get("secondary_window")),
    }
