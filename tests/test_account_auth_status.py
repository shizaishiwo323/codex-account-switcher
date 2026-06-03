import unittest

import app


class AccountAuthStatusTests(unittest.TestCase):
    def test_attach_auth_status_from_keepalive_status_file_payload(self):
        accounts = [
            {
                "id": "alpha",
                "label": "仓库池 alpha",
                "ok": True,
                "error": None,
                "usage": {},
            }
        ]
        status = {
            "accounts": {
                "alpha": {
                    "status": "auth_invalid",
                    "message": "后台 Codex 提示 refresh token 已失效，请重新登录这个账号。",
                    "updated_at": 1780437900,
                }
            }
        }

        app.attach_auth_statuses(accounts, status)

        self.assertEqual(accounts[0]["auth_status"]["status"], "auth_invalid")
        self.assertIn("重新登录", accounts[0]["auth_status"]["message"])

    def test_auth_status_from_refresh_token_error(self):
        message = "Your access token could not be refreshed because your refresh token was already used. Please log out and sign in again."

        status = app.auth_status_from_error(message)

        self.assertEqual(status["status"], "auth_invalid")
        self.assertIn("refresh token 已失效", status["message"])

    def test_frontend_renders_auth_status_warning(self):
        script_js = (app.ROOT / "static" / "script.js").read_text(encoding="utf-8")

        self.assertIn("function accountAuthStatusHtml(account)", script_js)
        self.assertIn("account.auth_status", script_js)
        self.assertIn("auth-warning", script_js)


if __name__ == "__main__":
    unittest.main()
