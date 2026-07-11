"""Tests for donelogger.

Run from the repo root with:

    python -m unittest discover

The elapsed-time tests mock ``time.perf_counter`` so durations are
deterministic (no ``sleep`` and no flaky timing assertions).
"""

import io
import logging
import os
import tempfile
import unittest
from unittest import mock

import donelogger.donelogger as dl
from donelogger.donelogger import DoneloggerFormatter, getLogger


def fmt_msg(formatter, msg, level=logging.INFO):
    """Render a single message through ``formatter`` and return the string."""
    record = logging.LogRecord("test", level, "x.py", 1, msg, None, None)
    return formatter.format(record)


class TestElapsedAdaptive(unittest.TestCase):
    def setUp(self):
        self.f = DoneloggerFormatter("%(message)s", elapsed_style="adaptive")

    def test_microseconds(self):
        self.assertEqual(self.f._format_elapsed(0.00005), "50us")
        self.assertEqual(self.f._format_elapsed(0.0005), "500us")

    def test_milliseconds(self):
        self.assertEqual(self.f._format_elapsed(0.001), "1.0ms")
        self.assertEqual(self.f._format_elapsed(0.5), "500.0ms")
        self.assertEqual(self.f._format_elapsed(0.9999), "999.9ms")

    def test_seconds(self):
        self.assertEqual(self.f._format_elapsed(1.0), "1.000s")
        self.assertEqual(self.f._format_elapsed(12.5), "12.500s")
        self.assertEqual(self.f._format_elapsed(59.999), "59.999s")

    def test_minutes(self):
        self.assertEqual(self.f._format_elapsed(60.0), "1m00.00s")
        self.assertEqual(self.f._format_elapsed(75.4), "1m15.40s")
        self.assertEqual(self.f._format_elapsed(90.0), "1m30.00s")

    def test_hours(self):
        self.assertEqual(self.f._format_elapsed(3600.0), "1h00m00s")
        self.assertEqual(self.f._format_elapsed(3661.0), "1h01m01s")
        self.assertEqual(self.f._format_elapsed(4500.0), "1h15m00s")


class TestElapsedSeconds(unittest.TestCase):
    def setUp(self):
        self.f = DoneloggerFormatter("%(message)s", elapsed_style="seconds")

    def test_always_seconds(self):
        self.assertEqual(self.f._format_elapsed(0.0000227), "0.000s")
        self.assertEqual(self.f._format_elapsed(0.005), "0.005s")
        self.assertEqual(self.f._format_elapsed(1.003), "1.003s")
        self.assertEqual(self.f._format_elapsed(59.999), "59.999s")

    def test_minutes_still_split(self):
        self.assertEqual(self.f._format_elapsed(75.4), "1m15.400s")
        self.assertEqual(self.f._format_elapsed(4500.0), "75m00.000s")


class TestElapsedStyle(unittest.TestCase):
    def test_default_is_adaptive(self):
        self.assertEqual(DoneloggerFormatter("%(message)s").elapsed_style, "adaptive")

    def test_invalid_style_raises(self):
        with self.assertRaises(ValueError):
            DoneloggerFormatter("%(message)s", elapsed_style="bogus")


class TestPatterns(unittest.TestCase):
    def test_start_pattern_matches(self):
        for s in ["[Start]", "[start]", "[Go]", "[go]", "[Start:tag1]", "[Go:x]"]:
            self.assertIsNotNone(DoneloggerFormatter.start_pattern.match(s), s)

    def test_start_pattern_rejects(self):
        # Guards the '[S|s]' regression: '|' must NOT be a valid char in the class.
        for s in ["[Done]", "[|tart]", "[|o]", "[Startfoo]", "normal text", "no brackets"]:
            self.assertIsNone(DoneloggerFormatter.start_pattern.match(s), s)

    def test_done_pattern(self):
        self.assertIsNotNone(DoneloggerFormatter.done_pattern.match("[Done]"))
        self.assertIsNotNone(DoneloggerFormatter.done_pattern.match("[done:t]"))
        self.assertIsNone(DoneloggerFormatter.done_pattern.match("[|one]"))
        self.assertIsNone(DoneloggerFormatter.done_pattern.match("[Start]"))

    def test_trailing_bracket_not_consumed(self):
        # "[Go:test] comment]" -> only "[Go:test]" matches (non-greedy .*?).
        m = DoneloggerFormatter.start_pattern.match("[Go:test] comment]")
        self.assertEqual(m.group(), "[Go:test]")
        self.assertEqual(m.group(1), ":test")


class TestStartDoneFlow(unittest.TestCase):
    def test_start_emits_go_and_records_tag(self):
        f = DoneloggerFormatter("%(message)s")
        with mock.patch.object(dl.time, "perf_counter", return_value=100.0):
            out = fmt_msg(f, "[Start:job] building")
        self.assertEqual(out, "+[Go job] building")
        self.assertIn("job", f.tag2time)

    def test_done_reports_elapsed(self):
        f = DoneloggerFormatter("%(message)s", elapsed_style="adaptive")
        with mock.patch.object(dl.time, "perf_counter", side_effect=[100.0, 102.5]):
            fmt_msg(f, "[Start:job] go")
            out = fmt_msg(f, "[Done:job] fin")
        self.assertEqual(out, "-[Done job(2.500s)] fin")

    def test_default_tag_is_job(self):
        f = DoneloggerFormatter("%(message)s")
        with mock.patch.object(dl.time, "perf_counter", side_effect=[10.0, 11.0]):
            self.assertEqual(fmt_msg(f, "[Start]"), "+[Go Job] ")
            self.assertEqual(fmt_msg(f, "[Done]"), "-[Done Job(1.000s)] ")

    def test_done_without_start_is_error(self):
        f = DoneloggerFormatter("%(message)s")
        out = fmt_msg(f, "[Done:ghost] x")
        self.assertIn("*LOG ERROR* (ghost is not started)", out)


class TestPassthrough(unittest.TestCase):
    def test_non_info_untouched(self):
        f = DoneloggerFormatter("%(message)s")
        # A WARNING bypasses start/done handling entirely.
        self.assertEqual(fmt_msg(f, "[Start] x", level=logging.WARNING), "[Start] x")

    def test_plain_info_untouched(self):
        f = DoneloggerFormatter("%(message)s")
        self.assertEqual(fmt_msg(f, "just a normal message"), "just a normal message")

    def test_lazy_logging_arguments_are_supported(self):
        f = DoneloggerFormatter("%(message)s")
        record = logging.LogRecord(
            "test", logging.INFO, "x.py", 1, "[Start:%s] processing %s", ("job", "data"), None
        )
        self.assertEqual(f.format(record), "+[Go job] processing data")

    def test_format_does_not_mutate_record_for_other_handlers(self):
        f = DoneloggerFormatter("%(message)s")
        record = logging.LogRecord(
            "test", logging.INFO, "x.py", 1, "[Start:%s] processing", ("job",), None
        )
        self.assertEqual(f.format(record), "+[Go job] processing")
        self.assertEqual(record.msg, "[Start:%s] processing")
        self.assertEqual(record.args, ("job",))
        self.assertEqual(logging.Formatter("%(message)s").format(record), "[Start:job] processing")


class TestInstanceIsolation(unittest.TestCase):
    def test_tag2time_not_shared(self):
        f1 = DoneloggerFormatter("%(message)s")
        f2 = DoneloggerFormatter("%(message)s")
        with mock.patch.object(dl.time, "perf_counter", return_value=1.0):
            fmt_msg(f1, "[Start:a] x")
        self.assertIn("a", f1.tag2time)
        self.assertNotIn("a", f2.tag2time)


class TestGetLoggerIntegration(unittest.TestCase):
    def test_start_done_through_public_api(self):
        # End-to-end guard for the fmt/datefmt parameter wiring.
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            log = getLogger("test_integration_logger", fmt="%(message)s")
            log.info("[Start:x] a")
            log.info("[Done:x] b")
        out = buf.getvalue()
        self.assertIn("+[Go x] a", out)
        self.assertIn("-[Done x(", out)

    def test_file_handler_also_renders_elapsed_time(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logfile = os.path.join(tmpdir, "app.log")
            with mock.patch("sys.stdout", io.StringIO()):
                log = getLogger("test_file_logger", logfile=logfile)
                log.info("[Start:x] a")
                log.info("[Done:x] b")
                for handler in log.handlers:
                    handler.flush()
            with open(logfile, encoding="utf-8") as f:
                out = f.read()
            for handler in list(log.handlers):
                log.removeHandler(handler)
                handler.close()
        self.assertIn("+[Go x] a", out)
        self.assertIn("-[Done x(", out)


if __name__ == "__main__":
    unittest.main()
