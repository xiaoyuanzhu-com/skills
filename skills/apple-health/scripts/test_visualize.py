#!/usr/bin/env python3
"""Tests for visualize.py — HTML dashboard generator.

Self-contained unittest tests that invoke visualize.py as a subprocess,
feeding it synthetic JSON inputs and verifying the HTML output.

Run with: python3 test_visualize.py
Exit 0 = all pass, 1 = any fail.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VISUALIZE_PY = os.path.join(SCRIPT_DIR, "visualize.py")

# ---------------------------------------------------------------------------
# Synthetic JSON fixtures (minimal but valid for each mode)
# ---------------------------------------------------------------------------

SCAN_DATA = {
    "period": {"from": "2026-01-01", "to": "2026-01-30"},
    "trend_alerts": [
        {
            "metric": "step-count",
            "direction": "up",
            "change_pct": 42.5,
            "first_half_avg": 5200,
            "second_half_avg": 7412,
        }
    ],
    "anomalies": [
        {
            "metric": "step-count",
            "date": "2026-01-18",
            "value": 18432,
            "z_score": 2.81,
        }
    ],
    "correlations": [
        {
            "metric_a": "step-count",
            "metric_b": "active-energy-burned",
            "lag": 0,
            "r": 0.87,
            "p": 0.0001,
            "n": 30,
        }
    ],
    "consistency": {
        "bedtime_stdev_min": 38.2,
        "exercise_frequency": 0.73,
        "step_cv": 0.31,
    },
}

SLEEP_DATA = {
    "period": {"from": "2026-01-10", "to": "2026-01-16"},
    "nightly": [
        {
            "date": "2026-01-10",
            "total_hrs": 7.25,
            "deep_pct": 18.5,
            "core_pct": 55.0,
            "rem_pct": 26.5,
            "awake_min": 12.0,
            "bedtime_local": "2026-01-10T23:15:00",
            "waketime_local": "2026-01-11T06:30:00",
        },
        {
            "date": "2026-01-11",
            "total_hrs": 6.50,
            "deep_pct": 15.0,
            "core_pct": 60.0,
            "rem_pct": 25.0,
            "awake_min": 8.0,
            "bedtime_local": "2026-01-11T23:45:00",
            "waketime_local": "2026-01-12T06:15:00",
        },
    ],
    "averages": {
        "total_hrs": 6.88,
        "deep_pct": 16.75,
        "core_pct": 57.5,
        "rem_pct": 25.75,
        "awake_min": 10.0,
    },
    "nights_analyzed": 2,
}

ACTIVITY_DATA = {
    "period": {"from": "2026-01-10", "to": "2026-01-16"},
    "daily": [
        {
            "date": "2026-01-10",
            "steps": 8452,
            "active_kcal": 412.5,
            "exercise_min": 35.0,
            "distance_km": 6.2,
        },
        {
            "date": "2026-01-11",
            "steps": 6100,
            "active_kcal": 310.0,
            "exercise_min": 22.0,
            "distance_km": 4.5,
        },
    ],
    "averages": {
        "steps": 7276,
        "active_kcal": 361.25,
        "exercise_min": 28.5,
        "distance_km": 5.35,
    },
    "days_analyzed": 2,
}

HEART_DATA = {
    "period": {"from": "2026-01-01", "to": "2026-01-14"},
    "weekly_resting_hr": [
        {"week": "2026-W01", "avg": 58.3, "n": 7},
        {"week": "2026-W02", "avg": 56.1, "n": 7},
    ],
    "weekly_hrv": [
        {"week": "2026-W01", "avg": 45.2, "n": 7},
        {"week": "2026-W02", "avg": 48.7, "n": 7},
    ],
    "avg_resting_hr": 57.2,
    "avg_hrv": 46.95,
    "avg_walking_hr": 102.3,
}

CORRELATE_DATA = {
    "period": {"from": "2026-01-01", "to": "2026-01-30"},
    "target": "step-count",
    "lags": [0, 1, 2],
    "correlations": [
        {"metric_a": "step-count", "metric_b": "active-energy-burned", "lag": 0, "r": 0.91, "p": 0.0, "n": 30},
        {"metric_a": "step-count", "metric_b": "resting-heart-rate", "lag": 1, "r": -0.42, "p": 0.02, "n": 29},
        {"metric_a": "step-count", "metric_b": "sleep-hours", "lag": 0, "r": 0.28, "p": 0.14, "n": 28},
    ],
}

COMPARE_DATA = {
    "p1": "2025-12",
    "p2": "2026-01",
    "metrics": [
        {
            "name": "step-count",
            "p1_avg": 6100.0,
            "p2_avg": 7800.0,
            "delta": 1700.0,
            "delta_pct": 27.9,
            "p1_days": 31,
            "p2_days": 31,
        },
        {
            "name": "resting-heart-rate",
            "p1_avg": 62.0,
            "p2_avg": 58.5,
            "delta": -3.5,
            "delta_pct": -5.6,
            "p1_days": 31,
            "p2_days": 31,
        },
    ],
}

YEARLY_DATA = {
    "year": 2025,
    "monthly": [
        {
            "month": "2025-01",
            "steps_avg": 7200,
            "sleep_avg_hrs": 7.1,
            "resting_hr_avg": 59.0,
            "hrv_avg": 44.0,
            "exercise_total_min": 620,
            "active_kcal_total": 9800,
            "days_with_data": 31,
        },
        {
            "month": "2025-02",
            "steps_avg": 6800,
            "sleep_avg_hrs": 6.9,
            "resting_hr_avg": 60.0,
            "hrv_avg": 42.0,
            "exercise_total_min": 540,
            "active_kcal_total": 8900,
            "days_with_data": 28,
        },
    ]
    + [
        {
            "month": "2025-{:02d}".format(m),
            "steps_avg": None,
            "sleep_avg_hrs": None,
            "resting_hr_avg": None,
            "hrv_avg": None,
            "exercise_total_min": None,
            "active_kcal_total": None,
            "days_with_data": 0,
        }
        for m in range(3, 13)
    ],
    "bests": {
        "highest_step_day": {"date": "2025-01-15", "value": 18432},
        "longest_sleep": {"date": "2025-02-08", "value": 9.2},
        "lowest_resting_hr": {"date": "2025-01-22", "value": 52},
        "highest_hrv": {"date": "2025-01-10", "value": 68},
    },
    "worsts": {
        "lowest_step_day": {"date": "2025-02-14", "value": 1200},
        "shortest_sleep": {"date": "2025-01-31", "value": 3.8},
        "highest_resting_hr": {"date": "2025-02-01", "value": 72},
    },
}

REPORT_DATA = {
    "period": {"from": "2026-01-01", "to": "2026-01-30"},
    "executive_summary": {
        "categories": [
            {"name": "Sleep", "score": 3.5, "trend": "flat",
             "summary_value": 7.2, "unit": "hrs avg",
             "sparkline": [7.0, 7.5, 6.8, 7.2, 7.4, 7.1]},
            {"name": "Daily Steps", "score": 4.0, "trend": "up",
             "summary_value": 9200, "unit": "avg",
             "sparkline": [8000, 9000, 10000, 9500, 8500, 9200]},
        ]
    },
    "sleep": {
        "duration_stats": {
            "n": 30, "mean": 7.2, "median": 7.3, "stdev": 0.8,
            "cv": 0.11, "percentiles": {"p10": 6.0, "p25": 6.5, "p75": 7.8, "p90": 8.2},
            "min": {"value": 4.5, "date": "2026-01-15"},
            "max": {"value": 9.1, "date": "2026-01-08"},
            "dates": ["2026-01-01", "2026-01-02"], "values": [7.0, 7.5],
            "rolling_7d": [None, 7.1],
            "rolling_30d": [], "trend_slope": 0.01, "trend_direction": "flat",
            "day_of_week": {"Mon": 7.0, "Tue": 7.2, "Wed": 7.1, "Thu": 7.3,
                            "Fri": 6.8, "Sat": 7.5, "Sun": 7.4},
            "distribution": [{"from": 4.5, "to": 5.4, "count": 2}],
            "period_comparison": {"first_half_avg": 7.0, "second_half_avg": 7.4, "change_pct": 5.7}
        },
        "stage_averages": {"total_hrs": 7.2, "deep_pct": 17.5, "core_pct": 55.0, "rem_pct": 25.0, "awake_min": 12.0},
        "stage_trends": {"deep_pcts": [18, 17], "core_pcts": [55, 54], "rem_pcts": [25, 26]},
        "nightly": [{"date": "2026-01-01", "total_hrs": 7.0, "deep_pct": 18.0, "core_pct": 55.0, "rem_pct": 25.0, "awake_min": 10.0, "bedtime_local": "2026-01-01T23:15:00", "waketime_local": "2026-01-02T06:15:00"}],
        "bedtime_stats": {"stdev_minutes": 38.5, "values_minutes": [1395, 1410]},
        "nights_analyzed": 30
    },
    "heart": {
        "resting_hr_stats": {
            "n": 30, "mean": 58.5, "median": 58.0, "stdev": 3.2, "cv": 0.05,
            "percentiles": {"p10": 54, "p25": 56, "p75": 61, "p90": 63},
            "min": {"value": 52, "date": "2026-01-10"}, "max": {"value": 66, "date": "2026-01-20"},
            "dates": ["2026-01-01"], "values": [58],
            "rolling_7d": [None], "rolling_30d": [],
            "trend_slope": 0.05, "trend_direction": "flat",
            "day_of_week": {"Mon": 58, "Tue": 57, "Wed": 59, "Thu": 58, "Fri": 59, "Sat": 57, "Sun": 58},
            "distribution": [{"from": 52, "to": 55, "count": 5}],
            "period_comparison": {"first_half_avg": 57.5, "second_half_avg": 59.5, "change_pct": 3.5}
        },
        "hrv_stats": {
            "n": 30, "mean": 45.2, "median": 44.0, "stdev": 8.5, "cv": 0.19,
            "percentiles": {"p10": 34, "p25": 38, "p75": 52, "p90": 56},
            "min": {"value": 28, "date": "2026-01-15"}, "max": {"value": 62, "date": "2026-01-05"},
            "dates": ["2026-01-01"], "values": [45],
            "rolling_7d": [None], "rolling_30d": [],
            "trend_slope": -0.1, "trend_direction": "down",
            "day_of_week": {"Mon": 44, "Tue": 46, "Wed": 45, "Thu": 43, "Fri": 44, "Sat": 47, "Sun": 46},
            "distribution": [{"from": 28, "to": 32, "count": 3}],
            "period_comparison": {"first_half_avg": 47, "second_half_avg": 43, "change_pct": -8.5}
        },
        "hr_hrv_scatter": [{"date": "2026-01-01", "rhr": 58, "hrv": 45}],
        "weekly_resting_hr": [{"week": "2026-W01", "avg": 58.0, "n": 7}],
        "weekly_hrv": [{"week": "2026-W01", "avg": 45.0, "n": 7}]
    },
    "activity": {
        "steps_stats": {
            "n": 30, "mean": 9200, "median": 9000, "stdev": 3200, "cv": 0.35,
            "percentiles": {"p10": 4500, "p25": 6800, "p75": 11500, "p90": 13800},
            "min": {"value": 1200, "date": "2026-01-14"}, "max": {"value": 18000, "date": "2026-01-22"},
            "dates": ["2026-01-01"], "values": [9200],
            "rolling_7d": [None], "rolling_30d": [],
            "trend_slope": 50, "trend_direction": "up",
            "day_of_week": {"Mon": 9500, "Tue": 10000, "Wed": 9200, "Thu": 8800, "Fri": 8500, "Sat": 10500, "Sun": 7900},
            "distribution": [{"from": 1200, "to": 2900, "count": 2}],
            "period_comparison": {"first_half_avg": 8500, "second_half_avg": 9900, "change_pct": 16.5},
            "streak_7k": 8
        },
        "exercise_stats": {
            "n": 30, "mean": 28.5, "median": 30.0, "stdev": 15.0, "cv": 0.53,
            "percentiles": {"p10": 0, "p25": 15, "p75": 42, "p90": 50},
            "min": {"value": 0, "date": "2026-01-07"}, "max": {"value": 65, "date": "2026-01-18"},
            "dates": ["2026-01-01"], "values": [30],
            "rolling_7d": [None], "rolling_30d": [],
            "trend_slope": 0.3, "trend_direction": "flat",
            "day_of_week": {"Mon": 35, "Tue": 30, "Wed": 25, "Thu": 32, "Fri": 20, "Sat": 38, "Sun": 15},
            "distribution": [{"from": 0, "to": 7, "count": 4}],
            "period_comparison": {"first_half_avg": 26, "second_half_avg": 31, "change_pct": 19.2},
            "streak_any": 12
        },
        "energy_stats": {
            "n": 30, "mean": 380, "median": 370, "stdev": 95, "cv": 0.25,
            "percentiles": {"p10": 250, "p25": 310, "p75": 440, "p90": 510},
            "min": {"value": 180, "date": "2026-01-14"}, "max": {"value": 620, "date": "2026-01-22"},
            "dates": ["2026-01-01"], "values": [380],
            "rolling_7d": [None], "rolling_30d": [],
            "trend_slope": 2.0, "trend_direction": "up",
            "day_of_week": {"Mon": 400, "Tue": 390, "Wed": 370, "Thu": 380, "Fri": 350, "Sat": 420, "Sun": 340},
            "distribution": [{"from": 180, "to": 224, "count": 2}],
            "period_comparison": {"first_half_avg": 350, "second_half_avg": 410, "change_pct": 17.1}
        }
    },
    "interconnections": {
        "matrix": [{"metric": "step-count", "values": {"step-count": 1.0, "resting-heart-rate": -0.3}}],
        "metric_names": ["step-count", "resting-heart-rate"],
        "top_correlations": [{"metric_a": "step-count", "metric_b": "active-energy-burned", "r": 0.91, "p": 0.0001, "n": 30}]
    },
    "methodology": {"metrics_analyzed": 8, "days_in_period": 30, "generated_at": "2026-01-30"}
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_visualize(data_dict, mode):
    """Write data to a temp JSON file and run visualize.py as subprocess.

    Returns (stdout_str, stderr_str, returncode).
    """
    fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="viz_test_")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data_dict, f)

        result = subprocess.run(
            [sys.executable, VISUALIZE_PY, tmp_path, "--mode", mode],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout, result.stderr, result.returncode
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestScanOutput(unittest.TestCase):
    """Test 1: scan mode produces valid HTML with trend data."""

    def test_scan_output_is_valid_html(self):
        stdout, stderr, rc = _run_visualize(SCAN_DATA, "scan")
        self.assertEqual(rc, 0, f"visualize.py failed: {stderr}")
        self.assertIn("<html", stdout)
        self.assertIn("</html>", stdout)
        self.assertGreater(len(stdout), 500)
        # Should contain trend data
        self.assertIn("step-count", stdout)
        self.assertIn("42.5", stdout)
        # Should contain anomaly data
        self.assertIn("2026-01-18", stdout)


class TestSleepOutput(unittest.TestCase):
    """Test 2: sleep mode output contains sleep hours."""

    def test_sleep_output_has_data(self):
        stdout, stderr, rc = _run_visualize(SLEEP_DATA, "sleep")
        self.assertEqual(rc, 0, f"visualize.py failed: {stderr}")
        self.assertIn("<html", stdout)
        # The total_hrs values should be in the injected data
        self.assertIn("7.25", stdout)
        self.assertIn("6.5", stdout)
        # Averages
        self.assertIn("6.88", stdout)


class TestActivityOutput(unittest.TestCase):
    """Test 3: activity mode output contains step count."""

    def test_activity_output(self):
        stdout, stderr, rc = _run_visualize(ACTIVITY_DATA, "activity")
        self.assertEqual(rc, 0, f"visualize.py failed: {stderr}")
        self.assertIn("<html", stdout)
        # Should contain step data from the JSON
        self.assertIn("8452", stdout)
        self.assertIn("7276", stdout)


class TestModeInjected(unittest.TestCase):
    """Test 4: window.__MODE__ appears in output with correct value."""

    def test_mode_injected(self):
        for mode, data in [
            ("scan", SCAN_DATA),
            ("sleep", SLEEP_DATA),
            ("activity", ACTIVITY_DATA),
            ("heart", HEART_DATA),
            ("correlate", CORRELATE_DATA),
            ("compare", COMPARE_DATA),
            ("yearly", YEARLY_DATA),
            ("report", REPORT_DATA),
        ]:
            with self.subTest(mode=mode):
                stdout, stderr, rc = _run_visualize(data, mode)
                self.assertEqual(rc, 0, f"visualize.py --mode {mode} failed: {stderr}")
                # The mode should be injected as a JS string
                self.assertIn("window.__MODE__=", stdout)
                self.assertIn(f'"{mode}"', stdout)


class TestDataInjected(unittest.TestCase):
    """Test 5: window.__DATA__ appears in output with parseable JSON."""

    def test_data_injected(self):
        stdout, stderr, rc = _run_visualize(SCAN_DATA, "scan")
        self.assertEqual(rc, 0, f"visualize.py failed: {stderr}")
        self.assertIn("window.__DATA__=", stdout)

        # Extract the JSON between window.__DATA__= and ;window.__MODE__
        marker_start = "window.__DATA__="
        marker_end = ";window.__MODE__="
        idx_start = stdout.index(marker_start) + len(marker_start)
        idx_end = stdout.index(marker_end)
        json_str = stdout[idx_start:idx_end]

        # It should be valid JSON
        parsed = json.loads(json_str)
        self.assertIsInstance(parsed, dict)
        # Verify key fields survived the round-trip
        self.assertIn("trend_alerts", parsed)
        self.assertIn("correlations", parsed)
        self.assertEqual(parsed["period"]["from"], "2026-01-01")


class TestHeartOutput(unittest.TestCase):
    """Heart mode output includes resting HR and HRV."""

    def test_heart_output(self):
        stdout, stderr, rc = _run_visualize(HEART_DATA, "heart")
        self.assertEqual(rc, 0, f"visualize.py failed: {stderr}")
        self.assertIn("<html", stdout)
        self.assertIn("57.2", stdout)
        self.assertIn("46.95", stdout)


class TestCorrelateOutput(unittest.TestCase):
    """Correlate mode output includes correlation values."""

    def test_correlate_output(self):
        stdout, stderr, rc = _run_visualize(CORRELATE_DATA, "correlate")
        self.assertEqual(rc, 0, f"visualize.py failed: {stderr}")
        self.assertIn("<html", stdout)
        self.assertIn("0.91", stdout)
        self.assertIn("-0.42", stdout)


class TestCompareOutput(unittest.TestCase):
    """Compare mode output includes both periods."""

    def test_compare_output(self):
        stdout, stderr, rc = _run_visualize(COMPARE_DATA, "compare")
        self.assertEqual(rc, 0, f"visualize.py failed: {stderr}")
        self.assertIn("<html", stdout)
        self.assertIn("2025-12", stdout)
        self.assertIn("2026-01", stdout)
        self.assertIn("27.9", stdout)


class TestYearlyOutput(unittest.TestCase):
    """Yearly mode output includes year and bests."""

    def test_yearly_output(self):
        stdout, stderr, rc = _run_visualize(YEARLY_DATA, "yearly")
        self.assertEqual(rc, 0, f"visualize.py failed: {stderr}")
        self.assertIn("<html", stdout)
        self.assertIn("2025", stdout)
        self.assertIn("18432", stdout)


class TestReportOutput(unittest.TestCase):
    """Report mode produces valid HTML with premium report data."""

    def test_report_html_generated(self):
        stdout, stderr, rc = _run_visualize(REPORT_DATA, "report")
        self.assertEqual(rc, 0, f"visualize.py failed: {stderr}")
        self.assertIn("<!DOCTYPE html>", stdout)
        self.assertIn("window.__DATA__", stdout)
        self.assertIn('"report"', stdout)

    def test_report_contains_sections(self):
        stdout, _, rc = _run_visualize(REPORT_DATA, "report")
        self.assertEqual(rc, 0)
        self.assertIn("executive_summary", stdout)
        self.assertIn("7.2", stdout)
        self.assertIn("58.5", stdout)
        self.assertIn("9200", stdout)


class TestErrorHandling(unittest.TestCase):
    """Edge cases: bad input file, invalid mode."""

    def test_missing_input_file(self):
        result = subprocess.run(
            [sys.executable, VISUALIZE_PY, "/nonexistent/file.json", "--mode", "scan"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_invalid_mode(self):
        fd, tmp_path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump({"test": True}, f)
            result = subprocess.run(
                [sys.executable, VISUALIZE_PY, tmp_path, "--mode", "invalid"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertNotEqual(result.returncode, 0)
        finally:
            os.unlink(tmp_path)

    def test_empty_data(self):
        """Empty dict should still produce valid HTML (graceful degradation)."""
        stdout, stderr, rc = _run_visualize({}, "scan")
        self.assertEqual(rc, 0, f"visualize.py failed on empty data: {stderr}")
        self.assertIn("<html", stdout)
        self.assertIn("window.__DATA__", stdout)


# ---------------------------------------------------------------------------
# Run tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = unittest.main(verbosity=2, exit=False)
    sys.exit(0 if result.result.wasSuccessful() else 1)
