from __future__ import annotations

import json
import shutil
import subprocess
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
    ACCOUNTS,
    BACKUP_DIR,
    CODEX_APP_BUNDLE_ID,
    CODEX_APP_PATH,
    DEFAULT_AUTH_PATH,
    HOST,
    PORT,
    PUBLIC_MONITOR_HOSTS,
    QUERY_TIMEOUT,
)


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
USAGE_HISTORY_PATH = ROOT / "usage_history.json"
USAGE_SAMPLE_INTERVAL_SECONDS = 10 * 60
USAGE_HISTORY_SAMPLE_LIMIT = 90 * 24 * 6


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


def find_account(account_id: str) -> dict | None:
    for account in ACCOUNTS:
        if account["id"] == account_id:
            return account
    return None


def current_default_account_id() -> str | None:
    try:
        return load_auth(DEFAULT_AUTH_PATH).account_id
    except Exception:
        return None


def account_items() -> list[dict]:
    active_account_id = current_default_account_id()
    items_by_id = {}
    with ThreadPoolExecutor(max_workers=len(ACCOUNTS)) as executor:
        futures = {}
        for account in ACCOUNTS:
            item = {
                "id": account["id"],
                "label": account["label"],
                "path": str(account["auth_path"]),
                "can_switch": bool(account.get("can_switch")),
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

    return [items_by_id[account["id"]] for account in ACCOUNTS]


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
                    for account in ACCOUNTS
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
        account["can_switch"] = False
        account.pop("path", None)
        usage = account.get("usage")
        if isinstance(usage, dict):
            usage.pop("path", None)
    return safe_accounts


def download_filename(account: dict) -> str:
    stem = "".join(
        char if char.isalnum() or char in {"-", "_"} else "-"
        for char in str(account.get("id") or "account")
    ).strip("-")
    return f"{stem or 'account'}-auth.json"


def usage_sampler_loop() -> None:
    while True:
        try:
            sample_usage_history("timer")
        except Exception as exc:
            print(f"定时用量采样失败: {exc}")
        time.sleep(USAGE_SAMPLE_INTERVAL_SECONDS)


def codex_is_running() -> bool:
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


def switch_account(target: dict) -> dict:
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

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"auth-default-{stamp}.json"

    quit_codex()
    shutil.copy2(destination_path, backup_path)
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=str(destination_path.parent), prefix=".auth-switch-", suffix=".json") as tmp:
        tmp_path = Path(tmp.name)
    shutil.copy2(source_path, tmp_path)
    tmp_path.replace(destination_path)
    launch = open_codex()

    return {
        "switched_to": target["id"],
        "label": target["label"],
        "source": str(source_path),
        "destination": str(destination_path),
        "backup": str(backup_path),
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
        if path != "/api/switch":
            self.send_error(404)
            return
        if is_monitor_only_request(self):
            json_response(self, 403, {"ok": False, "error": "公网监控入口是只读模式，不能切换账号"})
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
            result = switch_account(target)
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
