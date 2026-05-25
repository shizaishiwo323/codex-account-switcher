from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from codex_usage import load_auth, query_usage
from config import ACCOUNTS, BACKUP_DIR, DEFAULT_AUTH_PATH, HOST, PORT, QUERY_TIMEOUT


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"


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


def quit_codex() -> None:
    subprocess.run(
        ["osascript", "-e", 'tell application "Codex" to quit'],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def open_codex() -> None:
    subprocess.run(
        ["open", "-a", "Codex"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


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
    open_codex()

    return {
        "switched_to": target["id"],
        "label": target["label"],
        "source": str(source_path),
        "destination": str(destination_path),
        "backup": str(backup_path),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/accounts":
            json_response(self, 200, {"accounts": account_items()})
            return
        if path == "/":
            path = "/index.html"
        static_path = (STATIC_DIR / path.lstrip("/")).resolve()
        if not str(static_path).startswith(str(STATIC_DIR.resolve())) or not static_path.exists():
            self.send_error(404)
            return
        content_type = "text/html; charset=utf-8"
        if static_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif static_path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
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
            json_response(self, 200, {"ok": True, "result": result, "accounts": account_items()})
        except Exception as exc:
            json_response(self, 400, {"ok": False, "error": str(exc)})


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Codex Account Switcher: http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
