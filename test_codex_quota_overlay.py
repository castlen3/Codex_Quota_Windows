import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone

import codex_quota_overlay
from codex_quota_overlay import (
    QuotaError,
    apply_token_response,
    build_snapshot,
    display_fields,
    fetch_usage_from_url,
    next_delay,
    quota_pace,
    window_data,
)


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


class CachedSnapshotTests(unittest.TestCase):
    def test_window_data_keeps_raw_reset_at(self):
        saved_at = datetime.fromtimestamp(1_800_000_000 - 3 * 86400, tz=timezone.utc)
        data = window_data(
            {
                "used_percent": 34,
                "limit_window_seconds": 604800,
                "reset_at": 1_800_000_000,
            },
            saved_at,
        )
        self.assertEqual(data["reset_at"], 1_800_000_000)

    def test_cached_row_recomputes_countdown_and_pace(self):
        saved_at = datetime.fromtimestamp(1_800_000_000 - 3 * 86400, tz=timezone.utc)
        snapshot = build_snapshot({
            "plan_type": "plus",
            "rate_limit": {
                "secondary_window": {
                    "used_percent": 34,
                    "limit_window_seconds": 604800,
                    "reset_at": 1_800_000_000,
                },
            },
        })
        cached = json.loads(json.dumps(snapshot))["weekly"]

        # Rendered half a day after the cache was written: the countdown and the
        # pace must move, not stay frozen at save time.
        render_at = datetime.fromtimestamp(1_800_000_000 - 3.5 * 86400, tz=timezone.utc)
        display = display_fields(cached, render_at)

        self.assertEqual(display["reset"], "3d 12h")
        self.assertEqual(display["pace"]["expected_remaining"], 50.0)
        self.assertEqual(display["pace"]["delta"], 16.0)
        self.assertEqual(display["pace"]["status"], "ahead")

    def test_legacy_cache_without_raw_fields_falls_back_to_stored_strings(self):
        legacy = {"reset": "5d 12h", "pace": {"status": "ahead", "delta": 9.2}}
        display = display_fields(legacy, datetime.now(timezone.utc))
        self.assertEqual(display["reset"], "5d 12h")
        self.assertEqual(display["pace"], legacy["pace"])

    def test_loader_accepts_a_cache_file_without_the_legacy_mode_field(self):
        snapshot = build_snapshot({
            "plan_type": "plus",
            "rate_limit": {
                "secondary_window": {
                    "used_percent": 34,
                    "limit_window_seconds": 604800,
                    "reset_at": 1_800_000_000,
                },
            },
        })
        path = os.path.join(tempfile.gettempdir(), "dsh_cache_round_trip.json")
        saved = codex_quota_overlay.CACHE_FILE
        codex_quota_overlay.CACHE_FILE = path
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f)
            self.assertEqual(codex_quota_overlay.load_cached_snapshot(), snapshot)
        finally:
            codex_quota_overlay.CACHE_FILE = saved
            try:
                os.remove(path)
            except OSError:
                pass


class CacheWriteTests(unittest.TestCase):
    def test_display_only_changes_do_not_rewrite_the_cache(self):
        snapshot = build_snapshot({
            "plan_type": "plus",
            "rate_limit": {
                "secondary_window": {
                    "used_percent": 34,
                    "limit_window_seconds": 604800,
                    "reset_at": 1_800_000_000,
                },
            },
        })
        path = os.path.join(tempfile.gettempdir(), "dsh_cache_write_test.json")
        saved_file = codex_quota_overlay.CACHE_FILE
        saved_sig = codex_quota_overlay._last_cache_signature
        codex_quota_overlay.CACHE_FILE = path
        codex_quota_overlay._last_cache_signature = None
        try:
            codex_quota_overlay.save_cached_snapshot(snapshot)

            with open(path, "w", encoding="utf-8") as f:
                f.write("sentinel")

            # Same quota, different clock: must not rewrite the file.
            codex_quota_overlay.save_cached_snapshot(dict(snapshot, updated="23:59:59"))
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), "sentinel")

            # A real quota change does rewrite it.
            changed = json.loads(json.dumps(snapshot))
            changed["weekly"]["used"] = 40
            codex_quota_overlay.save_cached_snapshot(changed)
            with open(path, encoding="utf-8") as f:
                self.assertNotEqual(f.read(), "sentinel")
        finally:
            codex_quota_overlay.CACHE_FILE = saved_file
            codex_quota_overlay._last_cache_signature = saved_sig
            try:
                os.remove(path)
            except OSError:
                pass


class FetchErrorTests(unittest.TestCase):
    def test_socket_timeout_is_classified_as_timeout(self):
        original = codex_quota_overlay.urllib.request.urlopen

        def fake_urlopen(req, context=None, timeout=None):
            raise socket.timeout("timed out")

        codex_quota_overlay.urllib.request.urlopen = fake_urlopen
        try:
            with self.assertRaises(QuotaError) as raised:
                fetch_usage_from_url("token", "https://example.invalid/usage")
            self.assertEqual(raised.exception.status, "timeout")
        finally:
            codex_quota_overlay.urllib.request.urlopen = original


class BackoffTests(unittest.TestCase):
    def test_backoff_grows_and_caps(self):
        self.assertEqual(next_delay(0), 30)
        self.assertEqual(next_delay(1), 60)
        self.assertEqual(next_delay(2), 120)
        self.assertEqual(next_delay(3), 240)
        self.assertEqual(next_delay(10), 300)

    def test_success_resets_the_streak(self):
        self.assertEqual(next_delay(0), 30)


class AuthMergeTests(unittest.TestCase):
    def test_write_when_the_file_is_unchanged(self):
        current = {
            "auth_mode": "chatgpt",
            "tokens": {"access_token": "old", "refresh_token": "r1"},
        }
        response = {"access_token": "new", "refresh_token": "r2"}
        payload, token, should_write = apply_token_response(current, response, "r1")

        self.assertTrue(should_write)
        self.assertEqual(token, "new")
        self.assertEqual(payload["tokens"]["access_token"], "new")
        self.assertEqual(payload["tokens"]["refresh_token"], "r2")
        self.assertEqual(payload["auth_mode"], "chatgpt")

    def test_concurrent_writer_wins_and_nothing_is_written(self):
        current = {"tokens": {"access_token": "cli-token", "refresh_token": "r9"}}
        payload, token, should_write = apply_token_response(
            current, {"access_token": "ours"}, "r1"
        )

        self.assertFalse(should_write)
        self.assertIsNone(payload)
        self.assertEqual(token, "cli-token")


class LogTrimTests(unittest.TestCase):
    def test_log_is_trimmed_to_the_kept_tail(self):
        path = os.path.join(tempfile.gettempdir(), "dsh_log_trim_test.log")
        saved = (codex_quota_overlay.LOG_FILE,
                 codex_quota_overlay.LOG_MAX_BYTES,
                 codex_quota_overlay.LOG_KEEP_LINES)
        codex_quota_overlay.LOG_FILE = path
        codex_quota_overlay.LOG_MAX_BYTES = 200
        codex_quota_overlay.LOG_KEEP_LINES = 5
        try:
            for i in range(200):
                codex_quota_overlay.log_error("blocked 403", f"line {i}")
            with open(path, encoding="utf-8") as f:
                lines = f.read().splitlines()
            self.assertLessEqual(len(lines), 7)
            self.assertTrue(lines[-1].endswith("line 199"))
        finally:
            codex_quota_overlay.LOG_FILE, codex_quota_overlay.LOG_MAX_BYTES, \
                codex_quota_overlay.LOG_KEEP_LINES = saved
            try:
                os.remove(path)
            except OSError:
                pass


class InstanceLockTests(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.gettempdir(), "dsh_overlay_lock_test.lock")
        self.saved = (codex_quota_overlay.LOCK_FILE,
                      codex_quota_overlay.msvcrt,
                      codex_quota_overlay._lock_fd)
        codex_quota_overlay.LOCK_FILE = self.path
        codex_quota_overlay._lock_fd = None
        try:
            os.remove(self.path)
        except OSError:
            pass

    def tearDown(self):
        codex_quota_overlay.release_instance_lock()
        codex_quota_overlay.LOCK_FILE, codex_quota_overlay.msvcrt, \
            codex_quota_overlay._lock_fd = self.saved
        try:
            os.remove(self.path)
        except OSError:
            pass

    def test_lock_can_be_reacquired_after_release(self):
        self.assertTrue(codex_quota_overlay.acquire_instance_lock())
        codex_quota_overlay.release_instance_lock()
        self.assertFalse(os.path.exists(self.path))
        self.assertTrue(codex_quota_overlay.acquire_instance_lock())

    def test_lock_holder_writes_its_pid_for_diagnostics(self):
        self.assertTrue(codex_quota_overlay.acquire_instance_lock())
        # Read through the lock's own descriptor: the locked byte range is not
        # readable through a second handle on Windows.
        fd = codex_quota_overlay._lock_fd
        os.lseek(fd, 0, os.SEEK_SET)
        self.assertEqual(os.read(fd, 32).decode().strip(), str(os.getpid()))

    def test_windows_lock_blocks_a_second_process(self):
        if not codex_quota_overlay.msvcrt:
            self.skipTest("Windows file locking is unavailable")

        project_dir = os.path.dirname(os.path.abspath(codex_quota_overlay.__file__))
        script = (
            "import sys, time; "
            f"sys.path.insert(0, {project_dir!r}); "
            "import codex_quota_overlay as m; "
            f"m.LOCK_FILE = {self.path!r}; "
            "ok = m.acquire_instance_lock(); "
            "time.sleep(3); "
            "sys.exit(0 if ok else 1)"
        )
        try:
            child = subprocess.Popen([sys.executable, "-c", script])
        except PermissionError:
            self.skipTest("cannot spawn a child process in this sandbox")
        time.sleep(1.0)
        try:
            self.assertFalse(codex_quota_overlay.acquire_instance_lock())
        finally:
            child.wait()
        self.assertEqual(child.returncode, 0)


class AlreadyRunningNoticeTests(unittest.TestCase):
    def test_message_box_is_called_with_four_arguments(self):
        # MessageBoxW is stdcall with four parameters. Passing three leaves the
        # stack unbalanced, so pin the arity down.
        calls = []

        class FakeUser32:
            def MessageBoxW(self, *args):
                calls.append(args)
                return 1

        class FakeWindll:
            user32 = FakeUser32()

        saved = codex_quota_overlay.ctypes.windll
        codex_quota_overlay.ctypes.windll = FakeWindll()
        try:
            codex_quota_overlay.notify_already_running()
        finally:
            codex_quota_overlay.ctypes.windll = saved

        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0]), 4)


if __name__ == "__main__":
    unittest.main()
