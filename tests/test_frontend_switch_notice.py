import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendSwitchNoticeTests(unittest.TestCase):
    def test_switch_sync_notice_uses_in_page_dialog_instead_of_browser_alert(self):
        index_html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        script_js = (ROOT / "static" / "script.js").read_text(encoding="utf-8")
        style_css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

        self.assertIn('id="switchSyncDialog"', index_html)
        self.assertIn("showSwitchSyncDialog(syncMessage)", script_js)
        self.assertIn("switch-sync-dialog", style_css)
        self.assertNotIn("window.alert(syncMessage)", script_js)


if __name__ == "__main__":
    unittest.main()
