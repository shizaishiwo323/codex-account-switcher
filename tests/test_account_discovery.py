import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_usage import format_window
from config import build_accounts, default_auth_path, default_search_root, server_host, server_port


class AccountDiscoveryTests(unittest.TestCase):
    def test_default_paths_use_windows_user_home_when_running_on_windows(self):
        home = Path("C:/Users/imgw")

        self.assertEqual(default_search_root(home=home), home)
        self.assertEqual(default_auth_path(home=home), home / ".codex" / "auth.json")

    def test_default_paths_can_be_overridden_for_windows_installations(self):
        root = Path("D:/CodexHomes")
        with patch.dict("os.environ", {"CODEX_ACCOUNT_SEARCH_ROOT": str(root)}):
            self.assertEqual(default_search_root(), root)
            self.assertEqual(default_auth_path(), root / ".codex" / "auth.json")

    def test_server_bindings_can_be_overridden_from_environment(self):
        with patch.dict(
            "os.environ",
            {
                "CODEX_SWITCHER_HOST": "0.0.0.0",
                "CODEX_SWITCHER_PORT": "9876",
            },
        ):
            self.assertEqual(server_host(), "0.0.0.0")
            self.assertEqual(server_port(), 9876)

    def test_invalid_port_override_falls_back_to_default(self):
        with patch.dict("os.environ", {"CODEX_SWITCHER_PORT": "not-a-port"}):
            self.assertEqual(server_port(), 8765)

    def test_build_accounts_discovers_codex_home_directories_with_auth_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            default_home = root / ".codex"
            known_home = root / ".codex-shizaishiwo0"
            new_home = root / ".codex-zshi0509"
            incomplete_home = root / ".codex-empty"

            for path in (default_home, known_home, new_home, incomplete_home):
                path.mkdir()
            for path in (default_home, known_home, new_home):
                (path / "auth.json").write_text("{}", encoding="utf-8")

            accounts = build_accounts(search_root=root)

        self.assertEqual(
            [account["id"] for account in accounts],
            ["default", "shizaishiwo0", "zshi0509"],
        )
        self.assertEqual(accounts[0]["label"], "默认配置")
        self.assertFalse(accounts[0]["can_switch"])
        self.assertEqual(accounts[1]["label"], "仓库池 0")
        self.assertTrue(accounts[1]["can_switch"])
        self.assertEqual(accounts[2]["label"], "仓库池 zshi0509")
        self.assertTrue(accounts[2]["can_switch"])
        self.assertEqual(accounts[2]["auth_path"], new_home / "auth.json")

    def test_build_accounts_applies_overrides_without_hiding_new_accounts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for dirname in (".codex", ".codex-alpha", ".codex-beta"):
                home = root / dirname
                home.mkdir()
                (home / "auth.json").write_text("{}", encoding="utf-8")

            accounts = build_accounts(
                search_root=root,
                overrides={
                    "alpha": {
                        "label": "自定义 Alpha",
                        "can_switch": False,
                    }
                },
            )

        by_id = {account["id"]: account for account in accounts}
        self.assertEqual(by_id["alpha"]["label"], "自定义 Alpha")
        self.assertFalse(by_id["alpha"]["can_switch"])
        self.assertIn("beta", by_id)
        self.assertEqual(by_id["beta"]["label"], "仓库池 beta")


class UsageWindowFormattingTests(unittest.TestCase):
    def test_weekly_window_shows_reset_date_even_when_it_is_primary(self):
        formatted = format_window(
            {
                "limit_window_seconds": 604800,
                "used_percent": 3,
                "reset_at": 1780603431,
            }
        )

        self.assertEqual(formatted["label"], "1周")
        self.assertEqual(formatted["remaining_percent"], 97)
        self.assertIn("月", formatted["reset"])

    def test_hourly_window_shows_reset_time(self):
        formatted = format_window(
            {
                "limit_window_seconds": 18000,
                "used_percent": 26,
                "reset_at": 1780015800,
            }
        )

        self.assertEqual(formatted["label"], "5小时")
        self.assertEqual(formatted["remaining_percent"], 74)
        self.assertIn(":", formatted["reset"])


if __name__ == "__main__":
    unittest.main()
