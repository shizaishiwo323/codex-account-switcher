import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from keepalive_control import (
    MODE_AUTO,
    MODE_OFF,
    MODE_ON,
    account_keepalive_payload,
    start_keepalive_session,
    update_auto_pause_from_usage,
)


def account_item(account_id, primary, secondary):
    return {
        "id": account_id,
        "label": account_id,
        "can_switch": True,
        "usage": {
            "primary": primary,
            "secondary": secondary,
        },
    }


class KeepaliveControlTests(unittest.TestCase):
    def test_auto_mode_pauses_until_weekly_reset_when_weekly_quota_is_empty(self):
        now = time.time()
        reset_at = now + 3 * 86400
        account = account_item(
            "empty-week",
            {"label": "5小时", "remaining_percent": 80},
            {"label": "1周", "remaining_percent": 0, "reset_at": reset_at},
        )
        state = {"mode": MODE_AUTO}

        update_auto_pause_from_usage(state, account, now=now)
        payload = account_keepalive_payload(account, state, running=True, now=now)

        self.assertEqual(state["auto_pause_until"], reset_at)
        self.assertFalse(payload["desired"])
        self.assertEqual(payload["reason"], "weekly_exhausted")

    def test_auto_mode_uses_weekly_window_even_for_free_accounts(self):
        now = time.time()
        reset_at = now + 5 * 86400
        account = account_item(
            "free",
            {"label": "1周", "remaining_percent": 0, "reset_at": reset_at},
            {"label": "-", "remaining_percent": None},
        )
        state = {"mode": MODE_AUTO}

        update_auto_pause_from_usage(state, account, now=now)
        payload = account_keepalive_payload(account, state, running=False, now=now)

        self.assertEqual(payload["weekly_remaining_percent"], 0)
        self.assertFalse(payload["desired"])
        self.assertEqual(payload["resume_at"], reset_at)

    def test_auto_mode_does_not_pause_when_only_five_hour_quota_is_empty(self):
        now = time.time()
        account = account_item(
            "five-hour-empty",
            {"label": "5小时", "remaining_percent": 0},
            {"label": "1周", "remaining_percent": 25, "reset_at": now + 86400},
        )
        state = {"mode": MODE_AUTO, "auto_pause_until": now + 10}

        update_auto_pause_from_usage(state, account, now=now)
        payload = account_keepalive_payload(account, state, running=False, now=now)

        self.assertNotIn("auto_pause_until", state)
        self.assertTrue(payload["desired"])
        self.assertEqual(payload["reason"], "auto")

    def test_manual_modes_override_auto_pause(self):
        now = time.time()
        account = account_item(
            "manual",
            {"label": "5小时", "remaining_percent": 80},
            {"label": "1周", "remaining_percent": 0, "reset_at": now + 86400},
        )

        on_payload = account_keepalive_payload(
            account,
            {"mode": MODE_ON, "auto_pause_until": now + 86400},
            running=False,
            now=now,
        )
        off_payload = account_keepalive_payload(
            account,
            {"mode": MODE_OFF, "auto_pause_until": now + 86400},
            running=True,
            now=now,
        )

        self.assertTrue(on_payload["desired"])
        self.assertEqual(on_payload["reason"], "manual_on")
        self.assertFalse(off_payload["desired"])
        self.assertEqual(off_payload["reason"], "manual_off")

    def test_start_keepalive_session_trusts_and_uses_shared_workdir(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex-alpha"
            codex_home.mkdir()
            auth_path = codex_home / "auth.json"
            auth_path.write_text("{}", encoding="utf-8")
            trusted_dir = (root / "workspace").resolve()
            trusted_dir.mkdir()
            account = {"id": "alpha", "auth_path": str(auth_path)}

            with (
                patch("keepalive_control.tmux_sessions", return_value=set()),
                patch("keepalive_control.subprocess.run") as run,
                patch.dict("os.environ", {"CODEX_TRUSTED_WORKDIR": str(trusted_dir)}),
            ):
                start_keepalive_session(account)

            command = run.call_args.args[0]
            self.assertEqual(command[:5], ["tmux", "new-session", "-d", "-s", "codex-alpha"])
            self.assertIn(f"--cd '{trusted_dir}'", command[-1])
            config = (codex_home / "config.toml").read_text(encoding="utf-8")
            self.assertIn(f'[projects."{trusted_dir}"]', config)
            self.assertIn('trust_level = "trusted"', config)


if __name__ == "__main__":
    unittest.main()
