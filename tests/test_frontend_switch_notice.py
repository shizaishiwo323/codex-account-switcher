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

    def test_account_summary_counts_only_switchable_pool_accounts(self):
        script_js = (ROOT / "static" / "script.js").read_text(encoding="utf-8")

        self.assertIn("const summaryAccounts = accounts.filter((account) => account.can_switch);", script_js)
        self.assertIn("return summaryAccounts.reduce((summary, account) => {", script_js)

    def test_switch_button_quota_check_includes_thirty_day_window(self):
        script_js = (ROOT / "static" / "script.js").read_text(encoding="utf-8")

        self.assertIn('const thirtyDayRemaining = windowRemainingByLabel(usage, "30天");', script_js)
        self.assertIn("return [thirtyDayRemaining, weeklyRemaining, fiveHourRemaining].some(", script_js)

    def test_switch_cards_include_update_auth_checkbox(self):
        script_js = (ROOT / "static" / "script.js").read_text(encoding="utf-8")

        self.assertIn('data-update-auth="${escapeHtml(account.id)}"', script_js)
        self.assertIn("const updateAuth = document.querySelector", script_js)
        self.assertIn("body: JSON.stringify({id, update_auth: updateAuth}),", script_js)


if __name__ == "__main__":
    unittest.main()
