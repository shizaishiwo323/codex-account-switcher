from pathlib import Path


HOST = "127.0.0.1"
PORT = 8765
QUERY_TIMEOUT = 60.0
CODEX_APP_BUNDLE_ID = "com.openai.codex"
CODEX_APP_PATH = Path("/Applications/Codex.app")

DEFAULT_AUTH_PATH = Path("/Users/wangbin/.codex/auth.json")

ACCOUNTS = [
    {
        "id": "default",
        "label": "默认配置",
        "auth_path": DEFAULT_AUTH_PATH,
        "can_switch": False,
    },
    {
        "id": "shizaishiwo323",
        "label": "仓库池 323",
        "auth_path": Path("/Users/wangbin/.codex-shizaishiwo323/auth.json"),
        "can_switch": True,
    },
    {
        "id": "shizaishiwo0",
        "label": "仓库池 0",
        "auth_path": Path("/Users/wangbin/.codex-shizaishiwo0/auth.json"),
        "can_switch": True,
    },
    {
        "id": "shizaishiwo123",
        "label": "仓库池 123",
        "auth_path": Path("/Users/wangbin/.codex-shizaishiwo123/auth.json"),
        "can_switch": True,
    },
]

BACKUP_DIR = Path(__file__).resolve().parent / "backups"
