#!/usr/bin/env python3
"""Tests for discover.py — Apple Health data discovery tool.

Self-contained test runner (no pytest needed).
Run with: python3 test_discover.py
Exit code 0 if all pass, 1 if any fail.
"""

import json
import os
import sys
import tempfile
import unittest

# Import discover module from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import discover


def make_metric_file(base_dir, year, month, day, metric_name, samples, date=None):
    """Helper: create a metric JSON file in the YYYY/MM/DD/ structure."""
    day_dir = os.path.join(base_dir, f"{year:04d}", f"{month:02d}", f"{day:02d}")
    os.makedirs(day_dir, exist_ok=True)
    if date is None:
        date = f"{year:04d}-{month:02d}-{day:02d}"
    data = {
        "date": date,
        "type": f"HKQuantityTypeIdentifier{metric_name.replace('-', '').title()}",
        "timezone": "Asia/Shanghai",
        "unit": "count",
        "samples": samples,
    }
    filepath = os.path.join(day_dir, f"{metric_name}.json")
    with open(filepath, "w") as f:
        json.dump(data, f)
    return filepath


def make_workout_file(base_dir, year, month, day, uuid, activity_type, duration_s=1800):
    """Helper: create a workout JSON file."""
    day_dir = os.path.join(base_dir, f"{year:04d}", f"{month:02d}", f"{day:02d}")
    os.makedirs(day_dir, exist_ok=True)
    data = {
        "uuid": uuid,
        "activity_type": activity_type,
        "start": f"{year:04d}-{month:02d}-{day:02d}T08:00:00.000Z",
        "end": f"{year:04d}-{month:02d}-{day:02d}T08:30:00.000Z",
        "duration_s": duration_s,
        "stats": {},
        "route": [],
    }
    filepath = os.path.join(day_dir, f"workout-{uuid}.json")
    with open(filepath, "w") as f:
        json.dump(data, f)
    return filepath


def sample(device="Watch7,1", value=100):
    """Helper: create a single quantity sample dict."""
    return {
        "start": "2025-01-01T00:00:00.000Z",
        "end": "2025-01-01T00:05:00.000Z",
        "value": value,
        "unit": "count",
        "type": "HKQuantityTypeIdentifierStepCount",
        "source": "com.apple.health.XXXX",
        "device": device,
    }


class TestEmptyDirectory(unittest.TestCase):
    """Empty directory should produce zero results."""

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = discover.scan(tmpdir)
            self.assertEqual(result["total_days"], 0)
            self.assertEqual(result["metrics"], {})
            self.assertEqual(result["workouts"]["count"], 0)
            self.assertEqual(result["workouts"]["types"], [])
            self.assertEqual(result["devices"], [])
            self.assertIsNone(result["date_range"]["earliest"])
            self.assertIsNone(result["date_range"]["latest"])
            self.assertEqual(result["gaps"], [])
            self.assertEqual(result["data_dir"], tmpdir)


class TestSingleDay(unittest.TestCase):
    """Single day with one metric file."""

    def test_single_day(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            make_metric_file(tmpdir, 2025, 1, 15, "step-count", [
                sample("Watch7,1", 100),
                sample("iPhone16,1", 50),
            ])
            result = discover.scan(tmpdir)
            self.assertEqual(result["total_days"], 1)
            self.assertEqual(result["date_range"]["earliest"], "2025-01-15")
            self.assertEqual(result["date_range"]["latest"], "2025-01-15")
            self.assertIn("step-count", result["metrics"])
            m = result["metrics"]["step-count"]
            self.assertEqual(m["first"], "2025-01-15")
            self.assertEqual(m["last"], "2025-01-15")
            self.assertEqual(m["days_with_data"], 1)
            self.assertIn("Watch7,1", result["devices"])
            self.assertIn("iPhone16,1", result["devices"])
            self.assertEqual(result["gaps"], [])


class TestGapDetection(unittest.TestCase):
    """Gaps of 3+ days should be reported; gaps < 3 days should not."""

    def test_three_day_gap_reported(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Day 1: Jan 1
            make_metric_file(tmpdir, 2025, 1, 1, "step-count", [sample()])
            # Day 2: Jan 5 (gap of 3 days: Jan 2, 3, 4)
            make_metric_file(tmpdir, 2025, 1, 5, "step-count", [sample()])
            result = discover.scan(tmpdir)
            self.assertEqual(result["total_days"], 2)
            self.assertEqual(len(result["gaps"]), 1)
            gap = result["gaps"][0]
            self.assertEqual(gap["from"], "2025-01-02")
            self.assertEqual(gap["to"], "2025-01-04")
            self.assertEqual(gap["days"], 3)

    def test_two_day_gap_not_reported(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Day 1: Jan 1
            make_metric_file(tmpdir, 2025, 1, 1, "step-count", [sample()])
            # Day 2: Jan 3 (gap of 1 day: Jan 2 — not 3+)
            make_metric_file(tmpdir, 2025, 1, 3, "step-count", [sample()])
            result = discover.scan(tmpdir)
            self.assertEqual(result["gaps"], [])

    def test_exactly_at_boundary(self):
        """Gap of exactly 2 missing days should NOT be reported (< 3)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            make_metric_file(tmpdir, 2025, 1, 1, "step-count", [sample()])
            # Jan 2, Jan 3 missing — 2 missing days
            make_metric_file(tmpdir, 2025, 1, 4, "step-count", [sample()])
            result = discover.scan(tmpdir)
            # 2 missing days is < 3, so no gap reported
            self.assertEqual(result["gaps"], [])


class TestMultipleMetrics(unittest.TestCase):
    """Multiple metric types across multiple days."""

    def test_multiple_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            make_metric_file(tmpdir, 2025, 1, 1, "step-count", [sample()])
            make_metric_file(tmpdir, 2025, 1, 1, "heart-rate", [sample()])
            make_metric_file(tmpdir, 2025, 1, 2, "step-count", [sample()])
            # heart-rate not on day 2
            result = discover.scan(tmpdir)
            self.assertIn("step-count", result["metrics"])
            self.assertIn("heart-rate", result["metrics"])
            self.assertEqual(result["metrics"]["step-count"]["days_with_data"], 2)
            self.assertEqual(result["metrics"]["heart-rate"]["days_with_data"], 1)
            self.assertEqual(result["metrics"]["step-count"]["first"], "2025-01-01")
            self.assertEqual(result["metrics"]["step-count"]["last"], "2025-01-02")
            self.assertEqual(result["metrics"]["heart-rate"]["first"], "2025-01-01")
            self.assertEqual(result["metrics"]["heart-rate"]["last"], "2025-01-01")


class TestWorkoutDetection(unittest.TestCase):
    """Workout files should be counted and types extracted."""

    def test_workouts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            make_metric_file(tmpdir, 2025, 1, 1, "step-count", [sample()])
            make_workout_file(tmpdir, 2025, 1, 1, "aaa-111", "running")
            make_workout_file(tmpdir, 2025, 1, 1, "bbb-222", "cycling")
            make_workout_file(tmpdir, 2025, 1, 2, "ccc-333", "running")
            # Also add a metric file on day 2 so it counts as a day
            make_metric_file(tmpdir, 2025, 1, 2, "step-count", [sample()])
            result = discover.scan(tmpdir)
            self.assertEqual(result["workouts"]["count"], 3)
            self.assertIn("running", result["workouts"]["types"])
            self.assertIn("cycling", result["workouts"]["types"])


class TestNonJsonSkipped(unittest.TestCase):
    """Non-JSON files should be skipped without error."""

    def test_non_json_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            make_metric_file(tmpdir, 2025, 1, 1, "step-count", [sample()])
            # Create a markdown file in the root
            with open(os.path.join(tmpdir, "AGENTS.md"), "w") as f:
                f.write("# Agents\nSome text here.\n")
            # Create a non-JSON file inside a day directory
            day_dir = os.path.join(tmpdir, "2025", "01", "01")
            with open(os.path.join(day_dir, "notes.txt"), "w") as f:
                f.write("Just some notes\n")
            result = discover.scan(tmpdir)
            self.assertEqual(result["total_days"], 1)
            self.assertIn("step-count", result["metrics"])


class TestMalformedJsonSkipped(unittest.TestCase):
    """Malformed JSON files should be skipped without error."""

    def test_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            make_metric_file(tmpdir, 2025, 1, 1, "step-count", [sample()])
            day_dir = os.path.join(tmpdir, "2025", "01", "01")
            # Write invalid JSON
            with open(os.path.join(day_dir, "bad-metric.json"), "w") as f:
                f.write("{invalid json content")
            result = discover.scan(tmpdir)
            self.assertEqual(result["total_days"], 1)
            self.assertIn("step-count", result["metrics"])
            # bad-metric should not appear
            self.assertNotIn("bad-metric", result["metrics"])


class TestDeviceDetection(unittest.TestCase):
    """Devices should be collected from samples."""

    def test_multiple_devices(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            make_metric_file(tmpdir, 2025, 1, 1, "step-count", [
                sample("Watch7,1"),
                sample("iPhone16,1"),
            ])
            make_metric_file(tmpdir, 2025, 1, 2, "heart-rate", [
                sample("Watch7,1"),
                sample("Watch9,2"),
            ])
            result = discover.scan(tmpdir)
            devices = result["devices"]
            self.assertIn("Watch7,1", devices)
            self.assertIn("iPhone16,1", devices)
            self.assertIn("Watch9,2", devices)
            # No duplicates
            self.assertEqual(len(devices), len(set(devices)))


class TestDateRangeMultipleDays(unittest.TestCase):
    """Date range should span earliest to latest day."""

    def test_date_range(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            make_metric_file(tmpdir, 2024, 3, 15, "step-count", [sample()])
            make_metric_file(tmpdir, 2025, 11, 20, "step-count", [sample()])
            result = discover.scan(tmpdir)
            self.assertEqual(result["date_range"]["earliest"], "2024-03-15")
            self.assertEqual(result["date_range"]["latest"], "2025-11-20")


class TestMultipleGaps(unittest.TestCase):
    """Multiple gaps of 3+ days should all be reported."""

    def test_multiple_gaps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Jan 1, Jan 10, Jan 20
            make_metric_file(tmpdir, 2025, 1, 1, "step-count", [sample()])
            make_metric_file(tmpdir, 2025, 1, 10, "step-count", [sample()])
            make_metric_file(tmpdir, 2025, 1, 20, "step-count", [sample()])
            result = discover.scan(tmpdir)
            self.assertEqual(len(result["gaps"]), 2)
            # First gap: Jan 2 - Jan 9 (8 days)
            self.assertEqual(result["gaps"][0]["from"], "2025-01-02")
            self.assertEqual(result["gaps"][0]["to"], "2025-01-09")
            self.assertEqual(result["gaps"][0]["days"], 8)
            # Second gap: Jan 11 - Jan 19 (9 days)
            self.assertEqual(result["gaps"][1]["from"], "2025-01-11")
            self.assertEqual(result["gaps"][1]["to"], "2025-01-19")
            self.assertEqual(result["gaps"][1]["days"], 9)


class TestAbsoluteDataDir(unittest.TestCase):
    """data_dir in output should be an absolute path."""

    def test_absolute_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = discover.scan(tmpdir)
            self.assertTrue(os.path.isabs(result["data_dir"]))


class TestSortedOutputs(unittest.TestCase):
    """Devices and workout types should be sorted for determinism."""

    def test_sorted_devices(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            make_metric_file(tmpdir, 2025, 1, 1, "step-count", [
                sample("Zebra"),
                sample("Apple"),
                sample("Middle"),
            ])
            result = discover.scan(tmpdir)
            self.assertEqual(result["devices"], ["Apple", "Middle", "Zebra"])

    def test_sorted_workout_types(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            make_metric_file(tmpdir, 2025, 1, 1, "step-count", [sample()])
            make_workout_file(tmpdir, 2025, 1, 1, "a", "yoga")
            make_workout_file(tmpdir, 2025, 1, 1, "b", "cycling")
            make_workout_file(tmpdir, 2025, 1, 1, "c", "running")
            result = discover.scan(tmpdir)
            self.assertEqual(result["workouts"]["types"], ["cycling", "running", "yoga"])


# ---------------------------------------------------------------------------
# Integration test against real data (skipped if not found)
# ---------------------------------------------------------------------------
REAL_DATA_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "imports", "fitness", "apple-health",
)


class TestRealDataIntegration(unittest.TestCase):
    """Integration test against real Apple Health export data."""

    def setUp(self):
        self.real_dir = os.path.normpath(REAL_DATA_DIR)
        if not os.path.isdir(self.real_dir):
            self.skipTest(f"Real data not found at {self.real_dir}")

    def test_real_data_basic_structure(self):
        result = discover.scan(self.real_dir)
        # Should have a non-trivial number of days
        self.assertGreater(result["total_days"], 100, "Expected 100+ days of data")
        # Should have date range
        self.assertIsNotNone(result["date_range"]["earliest"])
        self.assertIsNotNone(result["date_range"]["latest"])
        self.assertLess(result["date_range"]["earliest"], result["date_range"]["latest"])
        # Should have some metrics
        self.assertGreater(len(result["metrics"]), 5, "Expected 5+ metric types")
        # step-count should be present in any Apple Health export
        self.assertIn("step-count", result["metrics"])
        # Should have devices
        self.assertGreater(len(result["devices"]), 0)
        # data_dir should be absolute
        self.assertTrue(os.path.isabs(result["data_dir"]))

    def test_real_data_valid_json_output(self):
        """The scan result should be JSON-serializable."""
        result = discover.scan(self.real_dir)
        output = json.dumps(result, indent=2)
        # Should round-trip
        parsed = json.loads(output)
        self.assertEqual(parsed["total_days"], result["total_days"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
