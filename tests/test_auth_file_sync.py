import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


def auth_bytes(account_id, access_token):
    return json.dumps(
        {
            "tokens": {
                "access_token": access_token,
                "refresh_token": f"refresh-{account_id}",
                "account_id": account_id,
            }
        },
        ensure_ascii=False,
    ).encode("utf-8")


def write_auth(path, account_id, access_token):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(auth_bytes(account_id, access_token))


class AuthFileSyncTests(unittest.TestCase):
    def test_switch_syncs_updated_default_auth_back_to_current_pool_account_with_both_backups(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            default_auth = root / ".codex" / "auth.json"
            pool_a_auth = root / ".codex-a" / "auth.json"
            pool_b_auth = root / ".codex-b" / "auth.json"
            backup_dir = root / "backups"

            write_auth(default_auth, "acct-a", "updated-default-token")
            write_auth(pool_a_auth, "acct-a", "old-pool-a-token")
            write_auth(pool_b_auth, "acct-b", "pool-b-token")

            accounts = [
                {"id": "default", "label": "默认配置", "auth_path": default_auth, "can_switch": False},
                {"id": "a", "label": "仓库池 A", "auth_path": pool_a_auth, "can_switch": True},
                {"id": "b", "label": "仓库池 B", "auth_path": pool_b_auth, "can_switch": True},
            ]

            with patch.object(app, "DEFAULT_AUTH_PATH", default_auth), \
                patch.object(app, "BACKUP_DIR", backup_dir), \
                patch.object(app, "get_accounts", return_value=accounts), \
                patch.object(app, "quit_codex"), \
                patch.object(app, "open_codex", return_value={"command": "open Codex"}):
                result = app.switch_account(accounts[2])

            self.assertEqual(pool_a_auth.read_bytes(), auth_bytes("acct-a", "updated-default-token"))
            self.assertEqual(default_auth.read_bytes(), auth_bytes("acct-b", "pool-b-token"))
            self.assertTrue(result["pre_switch_sync"]["changed"])
            self.assertEqual(result["pre_switch_sync"]["synced_to"], "a")

            backups = result["backups"]
            by_role = {backup["role"]: Path(backup["path"]) for backup in backups}
            self.assertEqual(
                by_role["default_before_sync_to_pool"].read_bytes(),
                auth_bytes("acct-a", "updated-default-token"),
            )
            self.assertEqual(
                by_role["pool_before_default_sync"].read_bytes(),
                auth_bytes("acct-a", "old-pool-a-token"),
            )
            self.assertEqual(
                by_role["before_switch"].read_bytes(),
                auth_bytes("acct-a", "updated-default-token"),
            )
            self.assertIn("a-to-b", by_role["before_switch"].name)
            self.assertNotIn("default_before_switch-b", by_role["before_switch"].name)

    def test_switch_does_not_sync_current_pool_account_when_files_are_identical(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            default_auth = root / ".codex" / "auth.json"
            pool_a_auth = root / ".codex-a" / "auth.json"
            pool_b_auth = root / ".codex-b" / "auth.json"
            backup_dir = root / "backups"

            write_auth(default_auth, "acct-a", "same-token")
            write_auth(pool_a_auth, "acct-a", "same-token")
            write_auth(pool_b_auth, "acct-b", "pool-b-token")

            accounts = [
                {"id": "default", "label": "默认配置", "auth_path": default_auth, "can_switch": False},
                {"id": "a", "label": "仓库池 A", "auth_path": pool_a_auth, "can_switch": True},
                {"id": "b", "label": "仓库池 B", "auth_path": pool_b_auth, "can_switch": True},
            ]

            with patch.object(app, "DEFAULT_AUTH_PATH", default_auth), \
                patch.object(app, "BACKUP_DIR", backup_dir), \
                patch.object(app, "get_accounts", return_value=accounts), \
                patch.object(app, "quit_codex"), \
                patch.object(app, "open_codex", return_value={"command": "open Codex"}):
                result = app.switch_account(accounts[2])

            self.assertFalse(result["pre_switch_sync"]["changed"])
            self.assertEqual(pool_a_auth.read_bytes(), auth_bytes("acct-a", "same-token"))
            self.assertNotIn("pool_before_default_sync", {backup["role"] for backup in result["backups"]})

    def test_uploaded_auth_replaces_target_only_when_different_and_backs_up_both_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target_auth = root / ".codex-a" / "auth.json"
            backup_dir = root / "backups"
            write_auth(target_auth, "acct-a", "old-token")

            target = {"id": "a", "label": "仓库池 A", "auth_path": target_auth, "can_switch": True}
            uploaded = auth_bytes("acct-a", "new-token")

            with patch.object(app, "BACKUP_DIR", backup_dir):
                result = app.replace_account_auth(target, uploaded)

            self.assertTrue(result["changed"])
            self.assertEqual(target_auth.read_bytes(), uploaded)
            by_role = {backup["role"]: Path(backup["path"]) for backup in result["backups"]}
            self.assertEqual(by_role["target_before_upload"].read_bytes(), auth_bytes("acct-a", "old-token"))
            self.assertEqual(by_role["uploaded_auth"].read_bytes(), uploaded)

    def test_uploaded_auth_does_not_replace_target_when_file_is_identical(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target_auth = root / ".codex-a" / "auth.json"
            backup_dir = root / "backups"
            payload = auth_bytes("acct-a", "same-token")
            target_auth.parent.mkdir(parents=True)
            target_auth.write_bytes(payload)

            target = {"id": "a", "label": "仓库池 A", "auth_path": target_auth, "can_switch": True}

            with patch.object(app, "BACKUP_DIR", backup_dir):
                result = app.replace_account_auth(target, payload)

            self.assertFalse(result["changed"])
            self.assertEqual(target_auth.read_bytes(), payload)
            self.assertFalse(backup_dir.exists())


if __name__ == "__main__":
    unittest.main()
