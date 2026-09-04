import unittest

from codex_quota_overlay import QuotaError, build_snapshot, quota_pace


WEEK_SECONDS = 7 * 24 * 60 * 60


class BuildSnapshotTests(unittest.TestCase):
    def test_dual_window_response_splits_into_five_hour_and_weekly(self):
        snapshot = build_snapshot({
            "plan_type": "plus",
            "rate_limit": {
                "allowed": True,
                "primary_window": {
                    "used_percent": 12,
                    "limit_window_seconds": 18000,
                    "reset_at": 1_800_000_000,
                },
                "secondary_window": {
                    "used_percent": 34,
                    "limit_window_seconds": 604800,
                    "reset_at": 1_800_000_000,
                },
            },
        })

        self.assertEqual(snapshot["quota_mode"], "dual")
        self.assertEqual(snapshot["five_hour"]["remaining"], 88)
        self.assertEqual(snapshot["five_hour"]["used"], 12)
        self.assertEqual(snapshot["five_hour"]["seconds"], 18000)
        self.assertEqual(snapshot["weekly"]["remaining"], 66)
        self.assertEqual(snapshot["weekly"]["used"], 34)
        self.assertEqual(snapshot["weekly"]["seconds"], 604800)

    def test_windows_are_matched_by_size_not_position(self):
        snapshot = build_snapshot({
            "plan_type": "plus",
            "rate_limit": {
                "primary_window": {
                    "used_percent": 5,
                    "limit_window_seconds": 604800,
                    "reset_at": 1_800_000_000,
                },
                "secondary_window": {
                    "used_percent": 50,
                    "limit_window_seconds": 18000,
                    "reset_at": 1_800_000_000,
                },
            },
        })

        self.assertEqual(snapshot["five_hour"]["remaining"], 50)
        self.assertEqual(snapshot["weekly"]["remaining"], 95)

    def test_seven_day_only_response_has_no_five_hour_row(self):
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

        self.assertEqual(snapshot["quota_mode"], "dual")
        self.assertIsNone(snapshot["five_hour"])
        self.assertEqual(snapshot["weekly"]["remaining"], 88)

    def test_five_hour_only_response_falls_back_to_weekly_row(self):
        snapshot = build_snapshot({
            "plan_type": "plus",
            "rate_limit": {
                "primary_window": {
                    "used_percent": 12,
                    "limit_window_seconds": 18000,
                    "reset_at": 1_800_000_000,
                },
            },
        })

        self.assertIsNone(snapshot["five_hour"])
        self.assertEqual(snapshot["weekly"]["remaining"], 88)
        self.assertEqual(snapshot["weekly"]["seconds"], 18000)

    def test_no_windows_is_an_error(self):
        with self.assertRaises(QuotaError):
            build_snapshot({
                "plan_type": "plus",
                "rate_limit": {"allowed": True},
            })


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
