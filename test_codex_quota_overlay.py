import unittest

from codex_quota_overlay import build_snapshot, quota_pace


WEEK_SECONDS = 7 * 24 * 60 * 60


class BuildSnapshotTests(unittest.TestCase):
    def test_single_seven_day_primary_window_becomes_weekly_quota(self):
        snapshot = build_snapshot({
            "plan_type": "plus",
            "rate_limit": {
                "allowed": True,
                "primary_window": {
                    "used_percent": 12,
                    "limit_window_seconds": 604800,
                    "reset_at": 1_800_000_000,
                },
                "secondary_window": None,
            },
        })

        self.assertEqual(snapshot["quota_mode"], "weekly")
        self.assertEqual(snapshot["weekly"]["remaining"], 88)
        self.assertEqual(snapshot["weekly"]["used"], 12)
        self.assertNotIn("primary", snapshot)
        self.assertNotIn("secondary", snapshot)

    def test_explicit_weekly_window_is_supported(self):
        snapshot = build_snapshot({
            "plan_type": "plus",
            "rate_limit": {
                "weekly_window": {
                    "used_percent": 34,
                    "limit_window_seconds": 604800,
                    "reset_at": 1_800_000_000,
                },
            },
        })

        self.assertEqual(snapshot["weekly"]["remaining"], 66)


class QuotaPaceTests(unittest.TestCase):
    def test_midpoint_reports_ahead(self):
        pace = quota_pace(
            {
                "used_percent": 28,
                "limit_window_seconds": WEEK_SECONDS,
                "reset_at": WEEK_SECONDS,
            },
            now_epoch=WEEK_SECONDS / 2,
        )

        self.assertEqual(pace["expected_remaining"], 50.0)
        self.assertEqual(pace["delta"], 22.0)
        self.assertEqual(pace["status"], "ahead")
        self.assertEqual(pace["daily_percent"], 14.3)

    def test_midpoint_reports_over_pace(self):
        pace = quota_pace(
            {
                "used_percent": 62,
                "limit_window_seconds": WEEK_SECONDS,
                "reset_at": WEEK_SECONDS,
            },
            now_epoch=WEEK_SECONDS / 2,
        )

        self.assertEqual(pace["delta"], -12.0)
        self.assertEqual(pace["status"], "over")

    def test_small_delta_is_on_pace(self):
        pace = quota_pace(
            {
                "used_percent": 49.4,
                "limit_window_seconds": WEEK_SECONDS,
                "reset_at": WEEK_SECONDS,
            },
            now_epoch=WEEK_SECONDS / 2,
        )

        self.assertEqual(pace["status"], "on_pace")

    def test_missing_reset_is_unavailable(self):
        self.assertIsNone(quota_pace({"used_percent": 20}))


if __name__ == "__main__":
    unittest.main()
