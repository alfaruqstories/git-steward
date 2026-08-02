import unittest

from git_steward.dashboard import render_html


def _summary() -> dict:
    repos = []
    for i in range(3):
        repos.append(
            {
                "display_name": f"repo-{i}",
                "path": f"~/Code/repo-{i}",
                "branch": "main",
                "dirty": 2 if i == 1 else 0,
                "untracked": 0,
                "ahead": 1 if i == 2 else 0,
                "stash_count": 1 if i == 1 else 0,
                "blocked_reason": "status_error" if i == 0 else None,
            }
        )
    return {
        "finished_at": "2026-08-02T12:00:00+0100",
        "totals": {"repos": 3, "blocked_repos": 1, "dirty_repos": 1, "ahead_repos": 1, "stash_repos": 1},
        "repos": repos,
    }


class DashboardRenderTests(unittest.TestCase):
    def test_renders_empty_summary(self):
        out = render_html({})
        self.assertIn("Git Steward", out)
        self.assertIn("no blocked repos right now", out)

    def test_renders_sections_and_counts(self):
        out = render_html(_summary())
        self.assertIn("BLOCKED", out)
        self.assertIn("DIRTY", out)
        self.assertIn("CLEAN", out)
        self.assertIn("repo-0", out)
        self.assertIn("status error", out)

    def test_health_percentage_computed(self):
        out = render_html(_summary())
        self.assertIn("67%", out)

    def test_theme_toggle_present(self):
        out = render_html(_summary())
        self.assertIn('id="theme"', out)
        self.assertIn('data-theme="dark"', out)

    def test_trend_sparkline_only_with_data(self):
        no_trend = render_html(_summary())
        self.assertNotIn('class="spark"', no_trend)
        with_trend = render_html(_summary(), trend=[("2026-08-02T10:00:00+0100", 3), ("2026-08-02T11:00:00+0100", 2)])
        self.assertIn('class="spark"', with_trend)
        self.assertIn("2 scans", with_trend)

    def test_refresh_meta_respects_flag(self):
        self.assertIn('<meta http-equiv="refresh" content="60">', render_html(_summary()))
        self.assertNotIn('http-equiv="refresh"', render_html(_summary(), refresh_seconds=0))


if __name__ == "__main__":
    unittest.main()
