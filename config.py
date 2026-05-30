from pathlib import Path


HOST = "127.0.0.1"
PORT = 8765
QUERY_TIMEOUT = 60.0
KEEPALIVE_AUTO_WEEKLY_PAUSE = False
PUBLIC_MONITOR_HOSTS = {
    "codex-quota.shizaishiwo.com",
}
CODEX_APP_BUNDLE_ID = "com.openai.codex"
CODEX_APP_PATH = Path("/Applications/Codex.app")

DEFAULT_AUTH_PATH = Path("/Users/wangbin/.codex/auth.json")
ACCOUNT_SEARCH_ROOT = Path("/Users/wangbin")
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
