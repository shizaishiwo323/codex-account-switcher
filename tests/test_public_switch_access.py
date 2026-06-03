import unittest
from pathlib import Path

import app


ROOT = Path(__file__).resolve().parents[1]


class PublicSwitchAccessTests(unittest.TestCase):
    def test_public_account_payload_keeps_switch_capability_but_hides_keepalive_and_paths(self):
        accounts = [
            {
                "id": "pool-a",
                "label": "仓库池 A",
                "path": "/Users/wangbin/.codex-pool-a/auth.json",
                "can_switch": True,
                "can_upload": True,
                "keepalive": {"enabled": True},
                "usage": {
                    "path": "/Users/wangbin/.codex-pool-a/auth.json",
                    "primary": {"label": "1周", "remaining_percent": 50},
                },
            }
        ]

        safe_accounts = app.monitor_safe_accounts(accounts, monitor_only=True)

        self.assertTrue(safe_accounts[0]["can_switch"])
        self.assertTrue(safe_accounts[0]["can_upload"])
        self.assertEqual(safe_accounts[0]["keepalive"], {"enabled": False})
        self.assertNotIn("path", safe_accounts[0])
        self.assertNotIn("path", safe_accounts[0]["usage"])

    def test_public_frontend_does_not_disable_or_skip_switch_buttons(self):
        script_js = (ROOT / "static" / "script.js").read_text(encoding="utf-8")

        self.assertNotIn("公网只读监控不能切换账号", script_js)
        self.assertNotIn("const buttonDisabled = monitorOnly || switchDisabled", script_js)
        self.assertNotIn("function bindSwitchButtons() {\n  if (monitorOnly) return;", script_js)

    def test_public_switch_endpoint_is_not_blocked_by_monitor_host(self):
        app_py = (ROOT / "app.py").read_text(encoding="utf-8")

        self.assertNotIn("公网监控入口是只读模式，不能切换账号", app_py)
        self.assertIn('if path == "/api/keepalive":', app_py)
        self.assertIn("公网监控入口是只读模式，不能控制后台保活", app_py)


if __name__ == "__main__":
    unittest.main()
