from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from codex_usage import load_auth, query_usage
from config import (
    BACKUP_DIR,
    CODEX_APP_BUNDLE_ID,
    CODEX_APP_PATH,
    DEFAULT_AUTH_PATH,
    HOST,
    KEEPALIVE_AUTO_WEEKLY_PAUSE,
    PORT,
    PUBLIC_MONITOR_HOSTS,
    QUERY_TIMEOUT,
    get_accounts,
)
from keepalive_control import (
    MODE_AUTO,
    MODE_OFF,
    MODE_ON,
    KeepaliveState,
    start_keepalive_session,
    stop_keepalive_session,
)


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
USAGE_HISTORY_PATH = ROOT / "usage_history.json"
KEEPALIVE_STATE_PATH = ROOT / "keepalive_state.json"
KEEPALIVE_STATUS_PATH = ROOT / "keepalive_status.json"
USAGE_SAMPLE_INTERVAL_SECONDS = 10 * 60
USAGE_HISTORY_SAMPLE_LIMIT = 90 * 24 * 6
MAX_AUTH_UPLOAD_BYTES = 2 * 1024 * 1024
KEEPALIVE_STATE = KeepaliveState(KEEPALIVE_STATE_PATH, auto_pause_enabled=KEEPALIVE_AUTO_WEEKLY_PAUSE)


def normalize_host(host: str | None) -> str:
    if not host:
        return ""
    host = host.split(",", 1)[0].strip().lower()
    if host.startswith("["):
        return host[1:].split("]", 1)[0]
    return host.rsplit(":", 1)[0]


PUBLIC_MONITOR_HOST_SET = {
    normalize_host(host)
    for host in PUBLIC_MONITOR_HOSTS
    if normalize_host(host)
}


def request_hosts(handler: BaseHTTPRequestHandler) -> set[str]:
    return {
        host
        for host in (
            normalize_host(handler.headers.get("Host")),
            normalize_host(handler.headers.get("X-Forwarded-Host")),
        )
        if host
    }


def is_monitor_only_request(handler: BaseHTTPRequestHandler) -> bool:
    return bool(request_hosts(handler) & PUBLIC_MONITOR_HOST_SET)


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def read_body_bytes(handler: BaseHTTPRequestHandler, max_bytes: int = MAX_AUTH_UPLOAD_BYTES) -> bytes:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return b""
    if length > max_bytes:
        raise ValueError(f"上传文件过大，最大允许 {max_bytes // 1024 // 1024} MB")
    return handler.rfile.read(length)


def find_account(account_id: str) -> dict | None:
    for account in get_accounts():
        if account["id"] == account_id:
            return account
    return None


def current_default_account_id() -> str | None:
    try:
        return load_auth(DEFAULT_AUTH_PATH).account_id
    except Exception:
        return None


def auth_status_from_error(error: object) -> dict | None:
    text = str(error or "")
    lower_text = text.lower()
    auth_invalid = any(
        marker in lower_text
        for marker in (
            "access token could not be refreshed",
            "access token refresh failed",
            "refresh token was already used",
            "please log out and sign in again",
            "invalid_grant",
            "refresh_token is missing",
        )
    )
    if not auth_invalid:
        return None
    return {
        "status": "auth_invalid",
        "message": "账号 refresh token 已失效，请重新登录这个账号后再刷新。",
        "detail": text,
    }


def load_keepalive_status(path: Path = KEEPALIVE_STATUS_PATH) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"accounts": {}}
    if not isinstance(data, dict):
        return {"accounts": {}}
    accounts = data.get("accounts")
    if not isinstance(accounts, dict):
        accounts = {}
    return {"accounts": accounts}


def attach_auth_statuses(accounts: list[dict], status_payload: dict | None = None) -> None:
    status_accounts = {}
    if isinstance(status_payload, dict) and isinstance(status_payload.get("accounts"), dict):
        status_accounts = status_payload["accounts"]
    for account in accounts:
        status = status_accounts.get(account.get("id")) if isinstance(account.get("id"), str) else None
        if isinstance(status, dict) and status.get("status") == "auth_invalid":
            account["auth_status"] = {
                "status": "auth_invalid",
                "message": status.get("message") or "账号认证已失效，请重新登录这个账号后再刷新。",
                "detail": status.get("detail"),
                "updated_at": status.get("updated_at"),
            }
            continue
        error_status = auth_status_from_error(account.get("error"))
        if error_status:
            account["auth_status"] = error_status


def account_items() -> list[dict]:
    active_account_id = current_default_account_id()
    accounts = get_accounts()
    items_by_id = {}
    with ThreadPoolExecutor(max_workers=max(1, len(accounts))) as executor:
        futures = {}
        for account in accounts:
            item = {
                "id": account["id"],
                "label": account["label"],
                "path": str(account["auth_path"]),
                "can_switch": bool(account.get("can_switch")),
                "can_upload": bool(account.get("can_switch")),
                "is_active": False,
                "ok": False,
                "error": None,
                "usage": None,
            }
            items_by_id[account["id"]] = item
            futures[executor.submit(query_usage, account["auth_path"], QUERY_TIMEOUT)] = account

        for future in as_completed(futures):
            account = futures[future]
            item = items_by_id[account["id"]]
            try:
                usage = future.result()
                item["ok"] = True
                item["usage"] = usage
                item["is_active"] = bool(active_account_id and usage.get("account_id") == active_account_id)
            except Exception as exc:
                item["error"] = str(exc)
                error_status = auth_status_from_error(exc)
                if error_status:
                    item["auth_status"] = error_status

    items = [items_by_id[account["id"]] for account in accounts]
    KEEPALIVE_STATE.update_auto_pauses(items)
    KEEPALIVE_STATE.attach_payloads(items)
    if KEEPALIVE_STATE.stop_paused_auto_sessions(items):
        KEEPALIVE_STATE.attach_payloads(items)
    attach_auth_statuses(items, load_keepalive_status())
    return items


class UsageHistory:
    def __init__(self, path: Path, sample_limit: int) -> None:
        self.path = path
        self.sample_limit = sample_limit
        self.lock = threading.RLock()
        self.samples: list[dict] = []
        self.switches: list[dict] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                samples = data.get("samples")
                switches = data.get("switches")
                if isinstance(samples, list):
                    self.samples = [item for item in samples if isinstance(item, dict)]
                if isinstance(switches, list):
                    self.switches = [item for item in switches if isinstance(item, dict)]
        except Exception as exc:
            print(f"用量历史读取失败，将从空历史开始: {exc}")

    def save(self) -> None:
        payload = {
            "version": 1,
            "sample_interval_seconds": USAGE_SAMPLE_INTERVAL_SECONDS,
            "samples": self.samples[-self.sample_limit :],
            "switches": self.switches[-300:],
        }
        with tempfile.NamedTemporaryFile(
            "w",
            delete=False,
            dir=str(self.path.parent),
            prefix=".usage-history-",
            suffix=".json",
            encoding="utf-8",
        ) as tmp:
            tmp_path = Path(tmp.name)
            json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp_path.replace(self.path)

    @staticmethod
    def now_fields() -> dict:
        now = time.time()
        return {
            "timestamp": now,
            "time": datetime.fromtimestamp(now).astimezone().isoformat(timespec="seconds"),
        }

    @staticmethod
    def usage_point(account: dict) -> dict:
        usage = account.get("usage") if isinstance(account.get("usage"), dict) else {}
        primary = usage.get("primary") if isinstance(usage.get("primary"), dict) else {}
        return {
            "id": account.get("id"),
            "label": account.get("label"),
            "ok": bool(account.get("ok")),
            "error": account.get("error"),
            "is_active": bool(account.get("is_active")),
            "account_id": usage.get("account_id"),
            "usage_account_id": usage.get("usage_account_id"),
            "email": usage.get("email"),
            "name": usage.get("name"),
            "used_percent": primary.get("used_percent"),
            "remaining_percent": primary.get("remaining_percent"),
            "reset_at": primary.get("reset_at"),
            "limit_reached": usage.get("limit_reached"),
            "plan": usage.get("plan"),
        }

    def record_sample(self, accounts: list[dict], trigger: str) -> None:
        sample = {
            **self.now_fields(),
            "trigger": trigger,
            "active_account_id": next((account.get("id") for account in accounts if account.get("is_active")), None),
            "accounts": [self.usage_point(account) for account in accounts],
        }
        with self.lock:
            self.samples.append(sample)
            self.samples = self.samples[-self.sample_limit :]
            self.save()

    def record_switch(self, result: dict) -> None:
        marker = {
            **self.now_fields(),
            "account_id": result.get("switched_to"),
            "label": result.get("label"),
        }
        with self.lock:
            self.switches.append(marker)
            self.switches = self.switches[-300:]
            self.save()

    def payload(self) -> dict:
        with self.lock:
            return {
                "sample_interval_seconds": USAGE_SAMPLE_INTERVAL_SECONDS,
                "accounts": [
                    {"id": account["id"], "label": account["label"]}
                    for account in get_accounts()
                ],
                "samples": deepcopy(self.samples),
                "switches": deepcopy(self.switches),
            }


USAGE_HISTORY = UsageHistory(USAGE_HISTORY_PATH, USAGE_HISTORY_SAMPLE_LIMIT)


def sample_usage_history(trigger: str) -> list[dict]:
    accounts = account_items()
    USAGE_HISTORY.record_sample(accounts, trigger)
    return accounts


def monitor_safe_accounts(accounts: list[dict], monitor_only: bool) -> list[dict]:
    if not monitor_only:
        return accounts
    safe_accounts = deepcopy(accounts)
    for account in safe_accounts:
        account["keepalive"] = {"enabled": False}
        account.pop("path", None)
        usage = account.get("usage")
        if isinstance(usage, dict):
            usage.pop("path", None)
    return safe_accounts


def apply_keepalive_mode(target: dict, mode: str) -> list[dict]:
    KEEPALIVE_STATE.update_mode(target["id"], mode)
    if mode == MODE_ON:
        start_keepalive_session(target)
        return sample_usage_history("keepalive")
    if mode == MODE_OFF:
        stop_keepalive_session(target["id"])
        return sample_usage_history("keepalive")

    accounts = sample_usage_history("keepalive")
    target_item = next((account for account in accounts if account.get("id") == target["id"]), None)
    keepalive = target_item.get("keepalive") if isinstance(target_item, dict) else {}
    if isinstance(keepalive, dict) and keepalive.get("desired"):
        start_keepalive_session(target)
    else:
        stop_keepalive_session(target["id"])
    return sample_usage_history("keepalive")


def download_filename(account: dict) -> str:
    stem = "".join(
        char if char.isalnum() or char in {"-", "_"} else "-"
        for char in str(account.get("id") or "account")
    ).strip("-")
    return f"{stem or 'account'}-auth.json"


def backup_name_part(value: object) -> str:
    part = "".join(
        char if char.isalnum() or char in {"-", "_"} else "-"
        for char in str(value or "unknown")
    ).strip("-")
    return part or "unknown"


def auth_files_equal(left: Path, right: Path) -> bool:
    return left.read_bytes() == right.read_bytes()


def atomic_write_bytes(destination_path: Path, data: bytes, prefix: str) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb",
            delete=False,
            dir=str(destination_path.parent),
            prefix=prefix,
            suffix=".json",
        ) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        tmp_path.replace(destination_path)
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


def backup_auth_file(path: Path, *, operation: str, role: str, account_id: str, stamp: str) -> dict:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    filename = (
        f"auth-{backup_name_part(operation)}-"
        f"{backup_name_part(role)}-"
        f"{backup_name_part(account_id)}-"
        f"{stamp}.json"
    )
    backup_path = BACKUP_DIR / filename
    shutil.copy2(path, backup_path)
    return {
        "role": role,
        "account_id": account_id,
        "source": str(path),
        "path": str(backup_path),
    }


def validate_auth_bytes(data: bytes) -> None:
    if not data:
        raise ValueError("上传的认证文件为空")
    with tempfile.NamedTemporaryFile("wb", delete=True, suffix=".json") as tmp:
        tmp.write(data)
        tmp.flush()
        load_auth(Path(tmp.name))


def pool_account_for_auth(auth_account_id: str | None, default_path: Path) -> dict | None:
    if not auth_account_id:
        return None
    for account in get_accounts():
        if not account.get("can_switch"):
            continue
        auth_path = Path(account["auth_path"]).expanduser().resolve()
        if auth_path == default_path:
            continue
        try:
            pool_auth = load_auth(auth_path)
        except Exception:
            continue
        if pool_auth.account_id == auth_account_id:
            return account
    return None


def sync_default_auth_to_current_pool(stamp: str, backups: list[dict]) -> dict:
    default_path = DEFAULT_AUTH_PATH.expanduser().resolve()
    default_auth = load_auth(default_path)
    current_account = pool_account_for_auth(default_auth.account_id, default_path)
    if not current_account:
        return {
            "changed": False,
            "reason": "没有找到和当前默认认证 account_id 匹配的账号池账号",
            "current_account_id": default_auth.account_id,
            "synced_to": None,
        }

    pool_path = Path(current_account["auth_path"]).expanduser().resolve()
    synced_to = str(current_account["id"])
    if auth_files_equal(default_path, pool_path):
        return {
            "changed": False,
            "reason": "默认认证和当前账号池认证完全一致，无需回写",
            "current_account_id": default_auth.account_id,
            "synced_to": synced_to,
            "pool_path": str(pool_path),
        }

    backups.append(
        backup_auth_file(
            default_path,
            operation="switch",
            role="default_before_sync_to_pool",
            account_id=synced_to,
            stamp=stamp,
        )
    )
    backups.append(
        backup_auth_file(
            pool_path,
            operation="switch",
            role="pool_before_default_sync",
            account_id=synced_to,
            stamp=stamp,
        )
    )
    atomic_write_bytes(pool_path, default_path.read_bytes(), ".auth-sync-")
    return {
        "changed": True,
        "reason": "默认认证比账号池认证更新，已回写到当前账号池",
        "current_account_id": default_auth.account_id,
        "synced_to": synced_to,
        "pool_path": str(pool_path),
    }


def switch_backup_account_part(pre_switch_sync: dict, target_id: str) -> str:
    source_id = pre_switch_sync.get("synced_to") if isinstance(pre_switch_sync, dict) else None
    if not source_id:
        source_id = pre_switch_sync.get("current_account_id") if isinstance(pre_switch_sync, dict) else None
    return f"{backup_name_part(source_id or 'unknown')}-to-{backup_name_part(target_id)}"


def replace_account_auth(target: dict, uploaded_data: bytes) -> dict:
    if not target.get("can_switch"):
        raise ValueError("只能上传覆盖账号池认证，不能远程覆盖默认配置")

    auth_path = Path(target["auth_path"]).expanduser().resolve()
    if not auth_path.exists() or not auth_path.is_file():
        raise FileNotFoundError(f"认证文件不存在: {auth_path}")
    load_auth(auth_path)
    validate_auth_bytes(uploaded_data)

    if uploaded_data == auth_path.read_bytes():
        return {
            "changed": False,
            "reason": "上传文件和目标账号池认证完全一致，无需覆盖",
            "account_id": target["id"],
            "path": str(auth_path),
            "backups": [],
        }

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    account_id = str(target["id"])
    backups = [
        backup_auth_file(
            auth_path,
            operation="upload",
            role="target_before_upload",
            account_id=account_id,
            stamp=stamp,
        )
    ]

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    uploaded_backup_path = BACKUP_DIR / (
        f"auth-upload-uploaded_auth-{backup_name_part(account_id)}-{stamp}.json"
    )
    uploaded_backup_path.write_bytes(uploaded_data)
    backups.append(
        {
            "role": "uploaded_auth",
            "account_id": account_id,
            "source": "upload",
            "path": str(uploaded_backup_path),
        }
    )

    atomic_write_bytes(auth_path, uploaded_data, ".auth-upload-")
    return {
        "changed": True,
        "reason": "上传文件和目标账号池认证不同，已备份两边并覆盖目标认证",
        "account_id": account_id,
        "path": str(auth_path),
        "backups": backups,
    }


def usage_sampler_loop() -> None:
    while True:
        try:
            sample_usage_history("timer")
        except Exception as exc:
            print(f"定时用量采样失败: {exc}")
        time.sleep(USAGE_SAMPLE_INTERVAL_SECONDS)


def codex_is_running() -> bool:
    if sys.platform == "win32":
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Codex.exe"],
            check=False,
            capture_output=True,
            text=True,
        )
        return "Codex.exe" in result.stdout

    result = subprocess.run(
        ["osascript", "-e", f'application id "{CODEX_APP_BUNDLE_ID}" is running'],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip().lower() == "true"


def wait_for_codex_running(expected: bool, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if codex_is_running() is expected:
            return True
        time.sleep(0.5)
    return codex_is_running() is expected


def quit_codex() -> None:
    if sys.platform == "win32":
        if not codex_is_running():
            return
        subprocess.run(
            ["taskkill", "/IM", "Codex.exe", "/T"],
            check=False,
            capture_output=True,
            text=True,
        )
        if not wait_for_codex_running(False, timeout=20.0):
            raise RuntimeError("Codex 桌面端没有在 20 秒内完全退出，请手动退出后重试")
        return

    subprocess.run(
        ["osascript", "-e", f'tell application id "{CODEX_APP_BUNDLE_ID}" to quit'],
        check=False,
        capture_output=True,
        text=True,
    )
    if not wait_for_codex_running(False, timeout=20.0):
        raise RuntimeError("Codex 桌面端没有在 20 秒内完全退出，请手动退出后重试")


def run_open_command(command: list[str]) -> str | None:
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode == 0:
        return None
    return (result.stderr or result.stdout or f"exit code {result.returncode}").strip()


def open_codex() -> dict[str, str]:
    if sys.platform == "win32":
        path = Path(CODEX_APP_PATH).expanduser()
        if path.exists():
            os.startfile(str(path))
            return {"command": f"start {path}", "path": str(path)}
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Start-Process Codex"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return {"command": "Start-Process Codex"}
        error = (result.stderr or result.stdout or f"exit code {result.returncode}").strip()
        raise RuntimeError(f"无法重新打开 Codex 桌面端: {error}")

    attempts = [
        ["open", "-b", CODEX_APP_BUNDLE_ID],
        ["open", str(CODEX_APP_PATH)],
        ["open", "-a", "Codex"],
    ]
    errors = []
    for command in attempts:
        error = run_open_command(command)
        if error:
            errors.append(f"{' '.join(command)}: {error}")
            continue
        if wait_for_codex_running(True, timeout=20.0):
            subprocess.run(
                ["osascript", "-e", f'tell application id "{CODEX_APP_BUNDLE_ID}" to activate'],
                check=False,
                capture_output=True,
                text=True,
            )
            return {"command": " ".join(command), "bundle_id": CODEX_APP_BUNDLE_ID}
        errors.append(f"{' '.join(command)}: 命令成功但 20 秒内没有检测到 Codex 正在运行")
    raise RuntimeError("Codex 桌面端启动失败：" + " | ".join(errors))


def skipped_auth_update_result(destination_path: Path) -> dict:
    default_auth = load_auth(destination_path)
    return {
        "changed": False,
        "skipped": True,
        "reason": "未勾选更新认证，已跳过默认认证回写检测",
        "current_account_id": default_auth.account_id,
    }


def switch_account(target: dict, *, update_current_auth: bool = False) -> dict:
    source_path = target["auth_path"].expanduser().resolve()
    destination_path = DEFAULT_AUTH_PATH.expanduser().resolve()
    if source_path == destination_path:
        raise ValueError("默认账号不需要切换")
    if not source_path.exists():
        raise FileNotFoundError(f"认证文件不存在: {source_path}")
    if not destination_path.exists():
        raise FileNotFoundError(f"默认认证文件不存在: {destination_path}")

    load_auth(source_path)
    load_auth(destination_path)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backups: list[dict] = []
    pre_switch_sync = (
        sync_default_auth_to_current_pool(stamp, backups)
        if update_current_auth
        else skipped_auth_update_result(destination_path)
    )
    switch_pair = switch_backup_account_part(pre_switch_sync, str(target["id"]))
    backups.append(
        backup_auth_file(
            destination_path,
            operation="switch",
            role="before_switch",
            account_id=switch_pair,
            stamp=stamp,
        )
    )

    quit_codex()
    atomic_write_bytes(destination_path, source_path.read_bytes(), ".auth-switch-")
    launch = open_codex()

    return {
        "switched_to": target["id"],
        "label": target["label"],
        "source": str(source_path),
        "destination": str(destination_path),
        "backup": backups[-1]["path"],
        "backups": backups,
        "pre_switch_sync": pre_switch_sync,
        "switch_from": pre_switch_sync.get("synced_to"),
        "switch_to": target["id"],
        "launch": launch,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def static_file(self, request_path: str) -> tuple[Path, str] | None:
        if request_path == "/":
            request_path = "/index.html"
        static_path = (STATIC_DIR / request_path.lstrip("/")).resolve()
        if not str(static_path).startswith(str(STATIC_DIR.resolve())) or not static_path.exists():
            return None
        content_type = "text/html; charset=utf-8"
        if static_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif static_path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        return static_path, content_type

    def serve_auth_download(self, account_id: str) -> None:
        target = find_account(account_id)
        if not target:
            json_response(self, 404, {"ok": False, "error": "未知账号"})
            return
        auth_path = target["auth_path"].expanduser().resolve()
        if not auth_path.exists() or not auth_path.is_file():
            json_response(self, 404, {"ok": False, "error": "认证文件不存在"})
            return

        data = auth_path.read_bytes()
        filename = download_filename(target)
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quote(filename)}')
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_auth_upload(self, account_id: str) -> None:
        target = find_account(account_id)
        if not target:
            json_response(self, 404, {"ok": False, "error": "未知账号"})
            return
        try:
            uploaded_data = read_body_bytes(self)
            result = replace_account_auth(target, uploaded_data)
            accounts = monitor_safe_accounts(sample_usage_history("upload"), is_monitor_only_request(self))
            json_response(self, 200, {"ok": True, "result": result, "accounts": accounts})
        except Exception as exc:
            json_response(self, 400, {"ok": False, "error": str(exc)})

    def do_HEAD(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/accounts/") and path.endswith("/auth.json"):
            account_id = unquote(path.removeprefix("/api/accounts/").removesuffix("/auth.json"))
            target = find_account(account_id)
            if not target:
                json_response(self, 404, {"ok": False, "error": "未知账号"})
                return
            auth_path = target["auth_path"].expanduser().resolve()
            if not auth_path.exists() or not auth_path.is_file():
                json_response(self, 404, {"ok": False, "error": "认证文件不存在"})
                return
            filename = download_filename(target)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quote(filename)}')
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(auth_path.stat().st_size))
            self.end_headers()
            return
        static_file = self.static_file(path)
        if not static_file:
            self.send_error(404)
            return
        static_path, content_type = static_file
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(static_path.stat().st_size))
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        monitor_only = is_monitor_only_request(self)
        if path == "/api/accounts":
            accounts = monitor_safe_accounts(sample_usage_history("manual"), monitor_only)
            json_response(self, 200, {"monitor_only": monitor_only, "accounts": accounts})
            return
        if path.startswith("/api/accounts/") and path.endswith("/auth.json"):
            account_id = unquote(path.removeprefix("/api/accounts/").removesuffix("/auth.json"))
            self.serve_auth_download(account_id)
            return
        if path == "/api/usage-history":
            payload = USAGE_HISTORY.payload()
            payload["monitor_only"] = monitor_only
            json_response(self, 200, payload)
            return
        static_file = self.static_file(path)
        if not static_file:
            self.send_error(404)
            return
        static_path, content_type = static_file
        data = static_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/accounts/") and path.endswith("/auth.json"):
            account_id = unquote(path.removeprefix("/api/accounts/").removesuffix("/auth.json"))
            self.serve_auth_upload(account_id)
            return

        if path == "/api/keepalive":
            if is_monitor_only_request(self):
                json_response(self, 403, {"ok": False, "error": "公网监控入口是只读模式，不能控制后台保活"})
                return
            try:
                payload = read_json(self)
                account_id = payload.get("id")
                mode = payload.get("mode")
                if not isinstance(account_id, str):
                    raise ValueError("缺少账号 id")
                if mode not in {MODE_AUTO, MODE_ON, MODE_OFF}:
                    raise ValueError("缺少有效保活模式")
                target = find_account(account_id)
                if not target:
                    raise ValueError(f"未知账号: {account_id}")
                if not target.get("can_switch"):
                    raise ValueError("这个账号没有后台保活控制")
                accounts = apply_keepalive_mode(target, mode)
                json_response(self, 200, {"ok": True, "accounts": accounts})
            except Exception as exc:
                json_response(self, 400, {"ok": False, "error": str(exc)})
            return

        if path != "/api/switch":
            self.send_error(404)
            return
        try:
            payload = read_json(self)
            account_id = payload.get("id")
            if not isinstance(account_id, str):
                raise ValueError("缺少账号 id")
            target = find_account(account_id)
            if not target:
                raise ValueError(f"未知账号: {account_id}")
            if not target.get("can_switch"):
                raise ValueError("这个账号不能作为切换目标")
            update_current_auth = bool(payload.get("update_auth"))
            result = switch_account(target, update_current_auth=update_current_auth)
            USAGE_HISTORY.record_switch(result)
            accounts = sample_usage_history("switch")
            json_response(self, 200, {"ok": True, "result": result, "accounts": accounts})
        except Exception as exc:
            json_response(self, 400, {"ok": False, "error": str(exc)})


def main() -> None:
    threading.Thread(target=usage_sampler_loop, daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Codex Account Switcher: http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
