import os
import sys
from pathlib import Path


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
QUERY_TIMEOUT = 60.0
KEEPALIVE_AUTO_WEEKLY_PAUSE = False
PUBLIC_MONITOR_HOSTS = {
    "codex-quota.shizaishiwo.com",
}
CODEX_APP_BUNDLE_ID = "com.openai.codex"


def server_host() -> str:
    return os.environ.get("CODEX_SWITCHER_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST


def server_port() -> int:
    value = os.environ.get("CODEX_SWITCHER_PORT")
    if not value:
        return DEFAULT_PORT
    try:
        port = int(value)
    except ValueError:
        return DEFAULT_PORT
    if 1 <= port <= 65535:
        return port
    return DEFAULT_PORT


def default_search_root(home: Path | None = None) -> Path:
    override = os.environ.get("CODEX_ACCOUNT_SEARCH_ROOT")
    if override:
        return Path(override).expanduser()
    return Path.home() if home is None else home


def default_auth_path(home: Path | None = None) -> Path:
    override = os.environ.get("CODEX_DEFAULT_AUTH_PATH")
    if override:
        return Path(override).expanduser()
    return default_search_root(home=home) / ".codex" / "auth.json"


def default_codex_app_path() -> Path:
    override = os.environ.get("CODEX_APP_PATH")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "Programs" / "Codex" / "Codex.exe"
        return Path.home() / "AppData" / "Local" / "Programs" / "Codex" / "Codex.exe"
    return Path("/Applications/Codex.app")


HOST = server_host()
PORT = server_port()
CODEX_APP_PATH = default_codex_app_path()
DEFAULT_AUTH_PATH = default_auth_path()
ACCOUNT_SEARCH_ROOT = default_search_root()
ACCOUNT_DIR_PREFIX = ".codex-"

ACCOUNT_OVERRIDES = {
    "shizaishiwo0": {"label": "仓库池 0"},
    "shizaishiwo123": {"label": "仓库池 123"},
    "shizaishiwo323": {"label": "仓库池 323"},
}


def account_label(account_id: str) -> str:
    if account_id.startswith("shizaishiwo"):
        suffix = account_id.removeprefix("shizaishiwo")
        if suffix:
            return f"仓库池 {suffix}"
    return f"仓库池 {account_id}"


def natural_sort_key(value: str) -> list[int | str]:
    parts: list[int | str] = []
    current = ""
    current_is_digit: bool | None = None
    for char in value:
        char_is_digit = char.isdigit()
        if current and char_is_digit != current_is_digit:
            parts.append(int(current) if current_is_digit else current)
            current = ""
        current += char
        current_is_digit = char_is_digit
    if current:
        parts.append(int(current) if current_is_digit else current)
    return parts


def discover_account_homes(search_root: Path = ACCOUNT_SEARCH_ROOT) -> list[Path]:
    try:
        candidates = list(search_root.iterdir())
    except OSError:
        return []

    homes = []
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        if not candidate.name.startswith(ACCOUNT_DIR_PREFIX):
            continue
        if (candidate / "auth.json").is_file():
            homes.append(candidate)
    return sorted(
        homes,
        key=lambda path: natural_sort_key(path.name.removeprefix(ACCOUNT_DIR_PREFIX)),
    )


def build_accounts(
    search_root: Path = ACCOUNT_SEARCH_ROOT,
    overrides: dict[str, dict] | None = None,
) -> list[dict]:
    account_overrides = ACCOUNT_OVERRIDES if overrides is None else overrides
    accounts = [
        {
            "id": "default",
            "label": "默认配置",
            "auth_path": search_root / ".codex" / "auth.json",
            "can_switch": False,
        }
    ]
    for home in discover_account_homes(search_root):
        account_id = home.name.removeprefix(ACCOUNT_DIR_PREFIX)
        if not account_id:
            continue
        account = {
            "id": account_id,
            "label": account_label(account_id),
            "auth_path": home / "auth.json",
            "can_switch": True,
        }
        account.update(account_overrides.get(account_id, {}))
        accounts.append(account)
    return accounts


def get_accounts() -> list[dict]:
    return build_accounts()


ACCOUNTS = get_accounts()

BACKUP_DIR = Path(__file__).resolve().parent / "backups"
