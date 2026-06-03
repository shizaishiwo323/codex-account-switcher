import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ensure_codex_keepalive.sh"


def write_executable(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class KeepaliveScriptTests(unittest.TestCase):
    def test_starts_all_pool_accounts_and_marks_project_trusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            tmux_log = root / "tmux.log"
            for name in (".codex-alpha", ".codex-beta", ".codex"):
                home = root / name
                home.mkdir()
                (home / "auth.json").write_text(
                    json.dumps({"tokens": {"account_id": name, "access_token": "token"}}),
                    encoding="utf-8",
                )
            write_executable(
                bin_dir / "tmux",
                f"""
                #!/usr/bin/env bash
                printf '%s\\n' "$*" >> "{tmux_log}"
                if [[ "$1" == "has-session" ]]; then exit 1; fi
                exit 0
                """,
            )
            write_executable(bin_dir / "codex", "#!/usr/bin/env bash\nexit 0\n")
            env = {
                **os.environ,
                "PATH": f"{bin_dir}:/usr/bin:/bin",
                "TMUX_BIN": str(bin_dir / "tmux"),
                "CODEX_BIN": str(bin_dir / "codex"),
                "PYTHON_BIN": sys.executable,
                "CODEX_ACCOUNT_SEARCH_ROOT": str(root),
                "CODEX_TRUSTED_WORKDIR": str(root),
                "KEEPALIVE_STATE_FILE": str(root / "keepalive_state.json"),
            }

            result = subprocess.run([str(SCRIPT)], env=env, check=False, capture_output=True, text=True)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            log = tmux_log.read_text(encoding="utf-8")
            self.assertIn("new-session -d -s codex-alpha", log)
            self.assertIn("new-session -d -s codex-beta", log)
            self.assertNotIn("codex-.codex", log)
            self.assertIn(f"--cd '{root}'", log)
            for account in ("alpha", "beta"):
                config = root / f".codex-{account}" / "config.toml"
                self.assertIn(f'[projects."{root}"]', config.read_text(encoding="utf-8"))
                self.assertIn('trust_level = "trusted"', config.read_text(encoding="utf-8"))

    def test_daily_ping_sends_hello_once_to_pool_sessions_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            tmux_log = root / "tmux.log"
            (root / ".codex-alpha").mkdir()
            (root / ".codex-alpha" / "auth.json").write_text(
                json.dumps({"tokens": {"account_id": "alpha", "access_token": "token"}}),
                encoding="utf-8",
            )
            (root / ".codex").mkdir()
            (root / ".codex" / "auth.json").write_text(
                json.dumps({"tokens": {"account_id": "default", "access_token": "default"}}),
                encoding="utf-8",
            )
            write_executable(
                bin_dir / "tmux",
                f"""
                #!/usr/bin/env bash
                printf '%s\\n' "$*" >> "{tmux_log}"
                if [[ "$1" == "has-session" ]]; then exit 0; fi
                exit 0
                """,
            )
            write_executable(bin_dir / "codex", "#!/usr/bin/env bash\nexit 0\n")
            env = {
                **os.environ,
                "PATH": f"{bin_dir}:/usr/bin:/bin",
                "TMUX_BIN": str(bin_dir / "tmux"),
                "CODEX_BIN": str(bin_dir / "codex"),
                "PYTHON_BIN": sys.executable,
                "CODEX_ACCOUNT_SEARCH_ROOT": str(root),
                "CODEX_TRUSTED_WORKDIR": str(root),
                "KEEPALIVE_STATE_FILE": str(root / "keepalive_state.json"),
                "KEEPALIVE_PING_STATE_FILE": str(root / "ping_state.json"),
                "KEEPALIVE_NOW_EPOCH": "1780437900",
            }

            first = subprocess.run([str(SCRIPT)], env=env, check=False, capture_output=True, text=True)
            second = subprocess.run([str(SCRIPT)], env=env, check=False, capture_output=True, text=True)

            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
            log = tmux_log.read_text(encoding="utf-8")
            self.assertEqual(log.count("send-keys -t codex-alpha"), 1)
            self.assertIn("send-keys -t codex-alpha 你好 Enter", log)
            self.assertNotIn("send-keys -t codex-", log.replace("send-keys -t codex-alpha", ""))

    def test_skips_invalid_auth_json_without_starting_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            tmux_log = root / "tmux.log"
            (root / ".codex-bad").mkdir()
            (root / ".codex-bad" / "auth.json").write_text("{bad json", encoding="utf-8")
            write_executable(
                bin_dir / "tmux",
                f"""
                #!/usr/bin/env bash
                printf '%s\\n' "$*" >> "{tmux_log}"
                if [[ "$1" == "has-session" ]]; then exit 1; fi
                exit 0
                """,
            )
            write_executable(bin_dir / "codex", "#!/usr/bin/env bash\nexit 0\n")
            env = {
                **os.environ,
                "PATH": f"{bin_dir}:/usr/bin:/bin",
                "TMUX_BIN": str(bin_dir / "tmux"),
                "CODEX_BIN": str(bin_dir / "codex"),
                "PYTHON_BIN": sys.executable,
                "CODEX_ACCOUNT_SEARCH_ROOT": str(root),
                "KEEPALIVE_STATE_FILE": str(root / "keepalive_state.json"),
            }

            result = subprocess.run([str(SCRIPT)], env=env, check=False, capture_output=True, text=True)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertFalse(tmux_log.exists())
            self.assertIn("invalid or expired-looking auth.json", result.stdout)

    def test_records_auth_invalid_status_from_tmux_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            tmux_log = root / "tmux.log"
            status_path = root / "keepalive_status.json"
            (root / ".codex-alpha").mkdir()
            (root / ".codex-alpha" / "auth.json").write_text(
                json.dumps({"tokens": {"account_id": "alpha", "access_token": "token"}}),
                encoding="utf-8",
            )
            write_executable(
                bin_dir / "tmux",
                f"""
                #!/usr/bin/env bash
                printf '%s\\n' "$*" >> "{tmux_log}"
                if [[ "$1" == "has-session" ]]; then exit 0; fi
                if [[ "$1" == "capture-pane" ]]; then
                  printf '%s\\n' 'Your access token could not be refreshed because your refresh token was already used. Please log out and sign in again.'
                  exit 0
                fi
                exit 0
                """,
            )
            write_executable(bin_dir / "codex", "#!/usr/bin/env bash\nexit 0\n")
            env = {
                **os.environ,
                "PATH": f"{bin_dir}:/usr/bin:/bin",
                "TMUX_BIN": str(bin_dir / "tmux"),
                "CODEX_BIN": str(bin_dir / "codex"),
                "PYTHON_BIN": sys.executable,
                "CODEX_ACCOUNT_SEARCH_ROOT": str(root),
                "CODEX_TRUSTED_WORKDIR": str(root),
                "KEEPALIVE_STATE_FILE": str(root / "keepalive_state.json"),
                "KEEPALIVE_STATUS_FILE": str(status_path),
            }

            result = subprocess.run([str(SCRIPT)], env=env, check=False, capture_output=True, text=True)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            state = json.loads(status_path.read_text(encoding="utf-8"))
            account_state = state["accounts"]["alpha"]
            self.assertEqual(account_state["status"], "auth_invalid")
            self.assertIn("refresh token 已失效", account_state["message"])


if __name__ == "__main__":
    unittest.main()
