import unittest

from codex_quota_overlay import build_snapshot


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


if __name__ == "__main__":
    unittest.main()
