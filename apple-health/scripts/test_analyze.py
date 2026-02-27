#!/usr/bin/env python3
"""Tests for analyze.py — MyLifeDB health data analysis engine.

Self-contained test runner using unittest with synthetic temp data.
Each test creates its own temporary directory structure mimicking the
YYYY/MM/DD/metric-name.json layout, runs the relevant analyze.py function,
and asserts correctness.

Run with: python3 test_analyze.py
Exit 0 = all pass, 1 = any fail.
"""

import json
import math
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta

# Import the module under test from the same directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze


# ---------------------------------------------------------------------------
# Helpers for building synthetic data directories
# ---------------------------------------------------------------------------


def _make_day_dir(base_dir, d):
    """Create YYYY/MM/DD directory and return its path."""
    day_dir = os.path.join(
        base_dir,
        f"{d.year:04d}",
        f"{d.month:02d}",
        f"{d.day:02d}",
    )
    os.makedirs(day_dir, exist_ok=True)
    return day_dir


def _write_metric(base_dir, d, metric_name, samples, tz="Asia/Shanghai",
                  hk_type="HKQuantityTypeIdentifier", unit="count"):
    """Write a metric JSON file for a given date."""
    day_dir = _make_day_dir(base_dir, d)
    data = {
        "date": d.isoformat(),
        "type": hk_type,
        "timezone": tz,
        "unit": unit,
        "samples": samples,
    }
    filepath = os.path.join(day_dir, f"{metric_name}.json")
    with open(filepath, "w") as f:
        json.dump(data, f)


def _quantity_sample(start_str, end_str, value, device="Watch7,1",
                     source="com.apple.health.test", unit="count",
                     hk_type="HKQuantityTypeIdentifierStepCount"):
    """Build a quantity-type sample dict."""
    return {
        "start": start_str,
        "end": end_str,
        "value": value,
        "unit": unit,
        "type": hk_type,
        "source": source,
        "device": device,
    }


def _sleep_sample(start_str, end_str, value, device="Watch7,1",
                  tz="Asia/Shanghai"):
    """Build a sleep-analysis category sample dict."""
    return {
        "start": start_str,
        "end": end_str,
        "value": value,
        "type": "HKCategoryTypeIdentifierSleepAnalysis",
        "source": "com.apple.health.test",
        "device": device,
        "metadata": {"HKTimeZone": tz},
    }


class BaseTestCase(unittest.TestCase):
    """Base class that creates and cleans up a temp directory."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="analyze_test_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test 1: Sum quantity metric (step-count)
# ---------------------------------------------------------------------------

class TestSumQuantityMetric(BaseTestCase):
    """step-count: sum of sample values = daily total."""

    def test_sum_quantity_metric(self):
        d = date(2026, 1, 15)
        samples = [
            _quantity_sample("2026-01-15T08:00:00Z", "2026-01-15T08:05:00Z", 200),
            _quantity_sample("2026-01-15T09:00:00Z", "2026-01-15T09:10:00Z", 350),
            _quantity_sample("2026-01-15T14:00:00Z", "2026-01-15T14:20:00Z", 450),
        ]
        _write_metric(self.tmpdir, d, "step-count", samples)

        result = analyze.aggregate_sum(self.tmpdir, "step-count", d, d)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[d], 1000.0, places=1)


# ---------------------------------------------------------------------------
# Test 2: Source deduplication
# ---------------------------------------------------------------------------

class TestSourceDedup(BaseTestCase):
    """Watch + overlapping iPhone → only Watch counted; non-overlapping iPhone added."""

    def test_source_dedup(self):
        d = date(2026, 1, 15)

        # Watch sample: 08:00-08:30, 500 steps
        watch_sample = _quantity_sample(
            "2026-01-15T08:00:00Z", "2026-01-15T08:30:00Z", 500,
            device="Watch7,1",
        )
        # iPhone sample overlapping Watch: 08:10-08:20, 200 steps (should be dropped)
        iphone_overlap = _quantity_sample(
            "2026-01-15T08:10:00Z", "2026-01-15T08:20:00Z", 200,
            device="iPhone15,3",
        )
        # iPhone sample NOT overlapping: 12:00-12:10, 100 steps (should be kept)
        iphone_no_overlap = _quantity_sample(
            "2026-01-15T12:00:00Z", "2026-01-15T12:10:00Z", 100,
            device="iPhone15,3",
        )

        all_samples = [watch_sample, iphone_overlap, iphone_no_overlap]
        deduped = analyze.dedup_samples(all_samples)

        # Should have Watch (500) + non-overlapping iPhone (100) = 600 total.
        total = sum(s["value"] for s in deduped)
        self.assertEqual(len(deduped), 2)
        self.assertAlmostEqual(total, 600.0, places=1)

    def test_dedup_via_aggregate(self):
        """End-to-end: aggregate_sum uses dedup for additive metrics."""
        d = date(2026, 1, 15)
        samples = [
            _quantity_sample("2026-01-15T08:00:00Z", "2026-01-15T08:30:00Z", 500,
                             device="Watch7,1"),
            _quantity_sample("2026-01-15T08:10:00Z", "2026-01-15T08:20:00Z", 200,
                             device="iPhone15,3"),
            _quantity_sample("2026-01-15T12:00:00Z", "2026-01-15T12:10:00Z", 100,
                             device="iPhone15,3"),
        ]
        _write_metric(self.tmpdir, d, "step-count", samples)

        result = analyze.aggregate_sum(self.tmpdir, "step-count", d, d)
        self.assertAlmostEqual(result[d], 600.0, places=1)


# ---------------------------------------------------------------------------
# Test 3: Sleep stages
# ---------------------------------------------------------------------------

class TestSleepStages(BaseTestCase):
    """Correct total_hrs, deep_pct, core_pct, rem_pct, awake_min."""

    def test_sleep_stages(self):
        d = date(2026, 1, 15)
        # Build sleep samples:
        # - asleepCore: 4 hours (240 min)
        # - asleepDeep: 1 hour (60 min)
        # - asleepREM: 1 hour (60 min)
        # - awake: 30 min
        # Total sleep = 6 hours, deep_pct = 16.67%, core_pct = 66.67%, rem_pct = 16.67%
        samples = [
            _sleep_sample("2026-01-14T17:00:00Z", "2026-01-14T21:00:00Z", "asleepCore"),
            _sleep_sample("2026-01-14T21:00:00Z", "2026-01-14T22:00:00Z", "asleepDeep"),
            _sleep_sample("2026-01-14T22:00:00Z", "2026-01-14T22:30:00Z", "awake"),
            _sleep_sample("2026-01-14T22:30:00Z", "2026-01-14T23:30:00Z", "asleepREM"),
        ]
        _write_metric(self.tmpdir, d, "sleep-analysis", samples,
                      hk_type="HKCategoryTypeIdentifierSleepAnalysis")

        raw = analyze.load_metric(self.tmpdir, "sleep-analysis", d, d)
        self.assertEqual(len(raw), 1)

        result = analyze._analyze_sleep_day(raw[0]["samples"], "Asia/Shanghai")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["total_hrs"], 6.0, places=1)
        self.assertAlmostEqual(result["deep_pct"], 16.7, delta=0.1)
        self.assertAlmostEqual(result["core_pct"], 66.7, delta=0.1)
        self.assertAlmostEqual(result["rem_pct"], 16.7, delta=0.1)
        self.assertAlmostEqual(result["awake_min"], 30.0, delta=0.1)


# ---------------------------------------------------------------------------
# Test 4: Sleep bedtime/waketime UTC→local conversion
# ---------------------------------------------------------------------------

class TestSleepBedtimeWaketime(BaseTestCase):
    """UTC→local conversion: UTC 17:00 → local 01:00 in Asia/Shanghai (+8h)."""

    def test_sleep_bedtime_waketime(self):
        d = date(2026, 1, 15)
        # Sleep from UTC 17:00 to UTC 23:00 on Jan 14
        # In Asia/Shanghai (+8h): bedtime = 01:00, waketime = 07:00 on Jan 15
        samples = [
            _sleep_sample("2026-01-14T17:00:00Z", "2026-01-14T20:00:00Z", "asleepCore"),
            _sleep_sample("2026-01-14T20:00:00Z", "2026-01-14T21:00:00Z", "asleepDeep"),
            _sleep_sample("2026-01-14T21:00:00Z", "2026-01-14T23:00:00Z", "asleepREM"),
        ]
        _write_metric(self.tmpdir, d, "sleep-analysis", samples,
                      hk_type="HKCategoryTypeIdentifierSleepAnalysis")

        raw = analyze.load_metric(self.tmpdir, "sleep-analysis", d, d)
        result = analyze._analyze_sleep_day(raw[0]["samples"], "Asia/Shanghai")

        self.assertIsNotNone(result)
        # Bedtime: UTC 17:00 + 8h = 01:00 local
        self.assertIn("01:00:00", result["bedtime_local"])
        self.assertIn("2026-01-15", result["bedtime_local"])
        # Waketime: UTC 23:00 + 8h = 07:00 local
        self.assertIn("07:00:00", result["waketime_local"])
        self.assertIn("2026-01-15", result["waketime_local"])


# ---------------------------------------------------------------------------
# Test 5: Trend detection
# ---------------------------------------------------------------------------

class TestTrendDetection(BaseTestCase):
    """7 days at 5000 steps + 7 days at 8000 steps → trend alert 'up'."""

    def test_trend_detection(self):
        # Create 14 days of step data: first 7 at 5000, next 7 at 8000.
        base_date = date(2026, 1, 1)

        for i in range(14):
            d = base_date + timedelta(days=i)
            value = 5000 if i < 7 else 8000
            samples = [
                _quantity_sample(
                    f"{d.isoformat()}T10:00:00Z",
                    f"{d.isoformat()}T10:30:00Z",
                    value,
                ),
            ]
            _write_metric(self.tmpdir, d, "step-count", samples)

        from_date = base_date
        to_date = base_date + timedelta(days=13)

        result = analyze.mode_scan(self.tmpdir, from_date, to_date)

        # Should have a trend alert for step-count going up.
        step_alerts = [a for a in result["trend_alerts"] if a["metric"] == "step-count"]
        self.assertTrue(len(step_alerts) > 0, "Expected a trend alert for step-count")
        self.assertEqual(step_alerts[0]["direction"], "up")

        # The change should be around +60% ((8000-5000)/5000 * 100).
        self.assertGreater(step_alerts[0]["change_pct"], 50)


# ---------------------------------------------------------------------------
# Test 6: Anomaly detection
# ---------------------------------------------------------------------------

class TestAnomalyDetection(BaseTestCase):
    """Inject one outlier day → detected as anomaly."""

    def test_anomaly_detection(self):
        base_date = date(2026, 1, 1)

        # 20 days at ~5000 steps, one day at 15000 (outlier).
        for i in range(20):
            d = base_date + timedelta(days=i)
            value = 5000
            if i == 10:
                value = 15000  # Outlier: 2 stdevs above mean
            samples = [
                _quantity_sample(
                    f"{d.isoformat()}T10:00:00Z",
                    f"{d.isoformat()}T10:30:00Z",
                    value,
                ),
            ]
            _write_metric(self.tmpdir, d, "step-count", samples)

        from_date = base_date
        to_date = base_date + timedelta(days=19)

        result = analyze.mode_scan(self.tmpdir, from_date, to_date)

        # Should detect the outlier on day 10 (Jan 11).
        step_anomalies = [a for a in result["anomalies"]
                          if a["metric"] == "step-count"]
        self.assertTrue(len(step_anomalies) > 0, "Expected at least one step anomaly")

        outlier_date = (base_date + timedelta(days=10)).isoformat()
        anomaly_dates = [a["date"] for a in step_anomalies]
        self.assertIn(outlier_date, anomaly_dates,
                      f"Expected anomaly on {outlier_date}, got {anomaly_dates}")


# ---------------------------------------------------------------------------
# Test 7: Correlation
# ---------------------------------------------------------------------------

class TestCorrelation(BaseTestCase):
    """Two perfectly correlated synthetic metrics → |r| > 0.9."""

    def test_correlation(self):
        base_date = date(2026, 1, 1)

        # Create two metrics: metric_a = i * 100, metric_b = i * 200 + 50.
        # These are perfectly linearly correlated (r = 1.0).
        for i in range(30):
            d = base_date + timedelta(days=i)
            val_a = (i + 1) * 100
            val_b = (i + 1) * 200 + 50

            _write_metric(self.tmpdir, d, "step-count", [
                _quantity_sample(
                    f"{d.isoformat()}T10:00:00Z",
                    f"{d.isoformat()}T10:30:00Z",
                    val_a,
                ),
            ])
            _write_metric(self.tmpdir, d, "active-energy-burned", [
                _quantity_sample(
                    f"{d.isoformat()}T10:00:00Z",
                    f"{d.isoformat()}T10:30:00Z",
                    val_b,
                    unit="kcal",
                    hk_type="HKQuantityTypeIdentifierActiveEnergyBurned",
                ),
            ])

        from_date = base_date
        to_date = base_date + timedelta(days=29)

        result = analyze.mode_correlate(
            self.tmpdir, from_date, to_date,
            target="step-count", lags=[0],
        )

        self.assertIn("correlations", result)
        # Find the correlation between step-count and active-energy-burned.
        matching = [c for c in result["correlations"]
                    if c["metric_b"] == "active-energy-burned"]
        self.assertTrue(len(matching) > 0,
                        "Expected correlation with active-energy-burned")
        self.assertGreater(abs(matching[0]["r"]), 0.9)

    def test_pearson_function(self):
        """Direct test of pearson() function with known data."""
        # Perfect positive correlation.
        x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        y = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
        r, p, n = analyze.pearson(x, y)
        self.assertAlmostEqual(r, 1.0, places=3)
        self.assertEqual(n, 10)

        # Perfect negative correlation.
        y_neg = [20, 18, 16, 14, 12, 10, 8, 6, 4, 2]
        r, p, n = analyze.pearson(x, y_neg)
        self.assertAlmostEqual(r, -1.0, places=3)

        # Not enough data.
        r, p, n = analyze.pearson([1, 2, 3], [4, 5, 6])
        self.assertEqual(r, 0.0)
        self.assertEqual(p, 1.0)


# ---------------------------------------------------------------------------
# Test 8: Compare mode
# ---------------------------------------------------------------------------

class TestCompareMode(BaseTestCase):
    """Two periods with different averages → correct delta_pct."""

    def test_compare_mode(self):
        # January 2026: step-count avg = 5000/day
        for day in range(1, 32):
            try:
                d = date(2026, 1, day)
            except ValueError:
                continue
            _write_metric(self.tmpdir, d, "step-count", [
                _quantity_sample(
                    f"{d.isoformat()}T10:00:00Z",
                    f"{d.isoformat()}T10:30:00Z",
                    5000,
                ),
            ])

        # February 2026: step-count avg = 8000/day
        for day in range(1, 29):
            try:
                d = date(2026, 2, day)
            except ValueError:
                continue
            _write_metric(self.tmpdir, d, "step-count", [
                _quantity_sample(
                    f"{d.isoformat()}T10:00:00Z",
                    f"{d.isoformat()}T10:30:00Z",
                    8000,
                ),
            ])

        result = analyze.mode_compare(self.tmpdir, "2026-01", "2026-02")

        self.assertIn("metrics", result)
        step_metrics = [m for m in result["metrics"] if m["name"] == "step-count"]
        self.assertTrue(len(step_metrics) > 0)

        m = step_metrics[0]
        self.assertAlmostEqual(m["p1_avg"], 5000.0, places=0)
        self.assertAlmostEqual(m["p2_avg"], 8000.0, places=0)
        self.assertAlmostEqual(m["delta"], 3000.0, places=0)
        # delta_pct should be 60% ((8000-5000)/5000 * 100)
        self.assertAlmostEqual(m["delta_pct"], 60.0, places=0)


# ---------------------------------------------------------------------------
# Test 9: Activity mode
# ---------------------------------------------------------------------------

class TestActivityMode(BaseTestCase):
    """Steps + active_kcal + exercise_min all computed."""

    def test_activity_mode(self):
        base_date = date(2026, 1, 10)

        for i in range(7):
            d = base_date + timedelta(days=i)
            ts = d.isoformat()

            # Step count
            _write_metric(self.tmpdir, d, "step-count", [
                _quantity_sample(
                    f"{ts}T08:00:00Z", f"{ts}T08:30:00Z",
                    6000 + i * 100,
                ),
            ])

            # Active energy
            _write_metric(self.tmpdir, d, "active-energy-burned", [
                _quantity_sample(
                    f"{ts}T08:00:00Z", f"{ts}T18:00:00Z",
                    300 + i * 10,
                    unit="kcal",
                    hk_type="HKQuantityTypeIdentifierActiveEnergyBurned",
                ),
            ])

            # Exercise time
            _write_metric(self.tmpdir, d, "apple-exercise-time", [
                _quantity_sample(
                    f"{ts}T08:00:00Z", f"{ts}T08:30:00Z",
                    30 + i * 5,
                    unit="min",
                    hk_type="HKQuantityTypeIdentifierAppleExerciseTime",
                ),
            ])

            # Distance
            _write_metric(self.tmpdir, d, "distance-walking-running", [
                _quantity_sample(
                    f"{ts}T08:00:00Z", f"{ts}T18:00:00Z",
                    4.0 + i * 0.5,
                    unit="km",
                    hk_type="HKQuantityTypeIdentifierDistanceWalkingRunning",
                ),
            ])

        result = analyze.mode_activity(
            self.tmpdir, base_date, base_date + timedelta(days=6),
        )

        self.assertEqual(result["days_analyzed"], 7)
        self.assertEqual(len(result["daily"]), 7)

        # Check first day.
        first = result["daily"][0]
        self.assertEqual(first["date"], "2026-01-10")
        self.assertAlmostEqual(first["steps"], 6000, places=0)
        self.assertAlmostEqual(first["active_kcal"], 300.0, places=0)
        self.assertAlmostEqual(first["exercise_min"], 30.0, delta=1)

        # Check averages exist and are reasonable.
        self.assertIn("steps", result["averages"])
        self.assertIn("active_kcal", result["averages"])
        self.assertIn("exercise_min", result["averages"])

        # Steps average: (6000+6100+...+6600)/7 = 6300
        self.assertAlmostEqual(result["averages"]["steps"], 6300.0, delta=10)


# ---------------------------------------------------------------------------
# Test 10: Heart mode
# ---------------------------------------------------------------------------

class TestHeartMode(BaseTestCase):
    """Weekly resting HR averages computed correctly."""

    def test_heart_mode(self):
        # Create 14 days of resting HR data across 2 ISO weeks.
        # Use dates in a single ISO week boundary.
        # 2026-01-05 (Mon) to 2026-01-11 (Sun) = week 2
        # 2026-01-12 (Mon) to 2026-01-18 (Sun) = week 3
        base_date = date(2026, 1, 5)  # Monday

        week1_values = [60, 62, 58, 61, 59, 63, 60]  # avg = 61.86 (approx 61.86)
        week2_values = [55, 56, 54, 57, 55, 53, 56]  # avg = 55.14 (approx 55.14)

        for i, val in enumerate(week1_values + week2_values):
            d = base_date + timedelta(days=i)
            ts = d.isoformat()
            _write_metric(self.tmpdir, d, "resting-heart-rate", [
                _quantity_sample(
                    f"{ts}T06:00:00Z", f"{ts}T06:45:00Z",
                    val,
                    unit="count/min",
                    hk_type="HKQuantityTypeIdentifierRestingHeartRate",
                ),
            ], unit="count/min")

        # Also add HRV data.
        for i in range(14):
            d = base_date + timedelta(days=i)
            ts = d.isoformat()
            _write_metric(self.tmpdir, d, "heart-rate-variability-sdnn", [
                _quantity_sample(
                    f"{ts}T06:00:00Z", f"{ts}T06:01:00Z",
                    40 + i * 2,
                    unit="ms",
                    hk_type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
                ),
            ], unit="ms")

        result = analyze.mode_heart(
            self.tmpdir, base_date, base_date + timedelta(days=13),
        )

        # Check weekly resting HR.
        weekly_rhr = result["weekly_resting_hr"]
        self.assertEqual(len(weekly_rhr), 2)

        # Week 1 average: (60+62+58+61+59+63+60)/7 ≈ 60.43
        w1 = weekly_rhr[0]
        self.assertAlmostEqual(w1["avg"], 60.43, delta=0.1)
        self.assertEqual(w1["n"], 7)

        # Week 2 average: (55+56+54+57+55+53+56)/7 ≈ 55.14
        w2 = weekly_rhr[1]
        self.assertAlmostEqual(w2["avg"], 55.14, delta=0.1)
        self.assertEqual(w2["n"], 7)

        # Check weekly HRV exists.
        self.assertTrue(len(result["weekly_hrv"]) > 0)

        # Check overall averages.
        self.assertIn("avg_resting_hr", result)
        self.assertIn("avg_hrv", result)


# ---------------------------------------------------------------------------
# Additional edge-case tests
# ---------------------------------------------------------------------------

class TestEdgeCases(BaseTestCase):
    """Additional edge cases to ensure robustness."""

    def test_empty_directory(self):
        """No data at all should return empty results."""
        result = analyze.aggregate_sum(
            self.tmpdir, "step-count",
            date(2026, 1, 1), date(2026, 1, 7),
        )
        self.assertEqual(len(result), 0)

    def test_missing_metric_file(self):
        """Days with some metrics but not the requested one."""
        d = date(2026, 1, 15)
        # Write only resting-heart-rate, then ask for step-count.
        _write_metric(self.tmpdir, d, "resting-heart-rate", [
            _quantity_sample("2026-01-15T06:00:00Z", "2026-01-15T06:45:00Z", 55),
        ])
        result = analyze.aggregate_sum(self.tmpdir, "step-count", d, d)
        self.assertEqual(len(result), 0)

    def test_mean_aggregation(self):
        """Mean aggregation for multi-sample metrics."""
        d = date(2026, 1, 15)
        samples = [
            _quantity_sample("2026-01-15T06:00:00Z", "2026-01-15T06:01:00Z", 40,
                             unit="ms"),
            _quantity_sample("2026-01-15T12:00:00Z", "2026-01-15T12:01:00Z", 60,
                             unit="ms"),
            _quantity_sample("2026-01-15T18:00:00Z", "2026-01-15T18:01:00Z", 50,
                             unit="ms"),
        ]
        _write_metric(self.tmpdir, d, "heart-rate-variability-sdnn", samples,
                      unit="ms")

        result = analyze.aggregate_mean(
            self.tmpdir, "heart-rate-variability-sdnn", d, d,
        )
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[d], 50.0, places=1)

    def test_no_watch_dedup(self):
        """When no Watch samples exist, all samples are kept."""
        samples = [
            _quantity_sample("2026-01-15T08:00:00Z", "2026-01-15T08:30:00Z", 200,
                             device="iPhone15,3"),
            _quantity_sample("2026-01-15T09:00:00Z", "2026-01-15T09:30:00Z", 300,
                             device="iPhone15,3"),
        ]
        deduped = analyze.dedup_samples(samples)
        total = sum(s["value"] for s in deduped)
        self.assertAlmostEqual(total, 500.0)
        self.assertEqual(len(deduped), 2)

    def test_aggregate_metric_auto_select(self):
        """aggregate_metric auto-selects sum for additive, mean for others."""
        d = date(2026, 1, 15)

        # step-count (additive) — should use sum.
        _write_metric(self.tmpdir, d, "step-count", [
            _quantity_sample("2026-01-15T08:00:00Z", "2026-01-15T08:30:00Z", 300),
            _quantity_sample("2026-01-15T09:00:00Z", "2026-01-15T09:30:00Z", 200),
        ])
        result = analyze.aggregate_metric(self.tmpdir, "step-count", d, d)
        self.assertAlmostEqual(result[d], 500.0)

        # heart-rate (mean metric) — should use mean.
        _write_metric(self.tmpdir, d, "heart-rate", [
            _quantity_sample("2026-01-15T08:00:00Z", "2026-01-15T08:01:00Z", 70,
                             unit="count/min"),
            _quantity_sample("2026-01-15T09:00:00Z", "2026-01-15T09:01:00Z", 80,
                             unit="count/min"),
        ], unit="count/min")
        result = analyze.aggregate_metric(self.tmpdir, "heart-rate", d, d)
        self.assertAlmostEqual(result[d], 75.0)

    def test_utc_to_local_conversion(self):
        """Direct test of _utc_to_local_str."""
        # UTC 17:00 + Asia/Shanghai (+8h) = 01:00 next day
        result = analyze._utc_to_local_str("2026-01-14T17:00:00Z", "Asia/Shanghai")
        self.assertEqual(result, "2026-01-15T01:00:00")

        # UTC 12:00 + America/New_York (-5h EST) = 07:00 same day (winter)
        result = analyze._utc_to_local_str("2026-01-15T12:00:00Z", "America/New_York")
        self.assertEqual(result, "2026-01-15T07:00:00")

    def test_utc_to_local_dst_aware(self):
        """DST-aware: summer in New York should be UTC-4, not UTC-5."""
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            self.skipTest("zoneinfo not available")
        # July 15 is during EDT (UTC-4), not EST (UTC-5)
        result = analyze._utc_to_local_str("2026-07-15T12:00:00Z", "America/New_York")
        self.assertEqual(result, "2026-07-15T08:00:00")

        # Sydney in July is AEST (UTC+10), not AEDT (UTC+11)
        result = analyze._utc_to_local_str("2026-07-15T12:00:00Z", "Australia/Sydney")
        self.assertEqual(result, "2026-07-15T22:00:00")


class TestSleepMode(BaseTestCase):
    """Integration test of mode_sleep."""

    def test_sleep_mode_integration(self):
        """mode_sleep returns correct nightly data and averages."""
        for i in range(3):
            d = date(2026, 1, 15) + timedelta(days=i)
            base_utc = f"2026-01-{14+i:02d}"
            samples = [
                _sleep_sample(f"{base_utc}T17:00:00Z", f"{base_utc}T21:00:00Z", "asleepCore"),
                _sleep_sample(f"{base_utc}T21:00:00Z", f"{base_utc}T22:00:00Z", "asleepDeep"),
                _sleep_sample(f"{base_utc}T22:00:00Z", f"{base_utc}T23:00:00Z", "asleepREM"),
                _sleep_sample(f"{base_utc}T23:00:00Z", f"{base_utc}T23:15:00Z", "awake"),
            ]
            _write_metric(self.tmpdir, d, "sleep-analysis", samples,
                          hk_type="HKCategoryTypeIdentifierSleepAnalysis")

        result = analyze.mode_sleep(
            self.tmpdir,
            date(2026, 1, 15),
            date(2026, 1, 17),
        )

        self.assertEqual(result["nights_analyzed"], 3)
        self.assertEqual(len(result["nightly"]), 3)

        # Each night: 4h core + 1h deep + 1h REM = 6h total.
        for night in result["nightly"]:
            self.assertAlmostEqual(night["total_hrs"], 6.0, places=1)

        # Averages should also be 6h.
        self.assertAlmostEqual(result["averages"]["total_hrs"], 6.0, places=1)


class TestYearlyMode(BaseTestCase):
    """Basic test of yearly mode."""

    def test_yearly_mode(self):
        """Yearly mode produces monthly breakdown and bests/worsts."""
        # Create data for Jan and Feb 2026 only.
        for month in [1, 2]:
            for day in range(1, 4):  # 3 days per month
                d = date(2026, month, day)
                ts = d.isoformat()
                step_val = 5000 if month == 1 else 8000

                _write_metric(self.tmpdir, d, "step-count", [
                    _quantity_sample(
                        f"{ts}T10:00:00Z", f"{ts}T10:30:00Z",
                        step_val,
                    ),
                ])

                _write_metric(self.tmpdir, d, "resting-heart-rate", [
                    _quantity_sample(
                        f"{ts}T06:00:00Z", f"{ts}T06:45:00Z",
                        60 if month == 1 else 55,
                        unit="count/min",
                    ),
                ], unit="count/min")

        result = analyze.mode_yearly(self.tmpdir, 2026)

        self.assertEqual(result["year"], 2026)
        self.assertEqual(len(result["monthly"]), 12)

        # January.
        jan = result["monthly"][0]
        self.assertEqual(jan["month"], "2026-01")
        self.assertAlmostEqual(jan["steps_avg"], 5000.0, delta=10)
        self.assertEqual(jan["days_with_data"], 3)

        # February.
        feb = result["monthly"][1]
        self.assertEqual(feb["month"], "2026-02")
        self.assertAlmostEqual(feb["steps_avg"], 8000.0, delta=10)

        # March through December should have no data.
        for i in range(2, 12):
            self.assertIsNone(result["monthly"][i]["steps_avg"])

        # Bests/worsts.
        self.assertIn("highest_step_day", result["bests"])
        self.assertIn("lowest_step_day", result["worsts"])
        self.assertAlmostEqual(
            result["bests"]["highest_step_day"]["value"], 8000, delta=10,
        )
        self.assertAlmostEqual(
            result["worsts"]["lowest_step_day"]["value"], 5000, delta=10,
        )


# ---------------------------------------------------------------------------
# Run tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Run with verbosity so individual test results are shown.
    result = unittest.main(verbosity=2, exit=False)
    sys.exit(0 if result.result.wasSuccessful() else 1)
