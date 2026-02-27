#!/usr/bin/env python3
"""Analyze Apple Health data in MyLifeDB format.

Provides multiple analysis modes (scan, sleep, activity, heart, correlate,
compare, yearly) over health data stored as YYYY/MM/DD/metric-name.json.

Usage:
    python3 analyze.py <data_dir> --mode=<mode> [options]

Modes:
    scan       Quick overview: trends, anomalies, correlations, consistency
    sleep      Sleep deep-dive: nightly totals, stages, bedtime, consistency
    activity   Steps, calories, exercise, distance
    heart      Resting HR, HRV, walking HR trends
    correlate  Cross-metric correlation with time lag
    compare    Two-period side-by-side comparison
    yearly     12-month annual summary

Output: JSON to stdout. Always.
"""

import argparse
import json
import math
import os
import sys
from collections import OrderedDict
from datetime import date, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    _HAS_ZONEINFO = True
except ImportError:
    _HAS_ZONEINFO = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Additive metrics: daily total = sum of samples. Needs source dedup.
ADDITIVE_METRICS = {
    "step-count",
    "active-energy-burned",
    "basal-energy-burned",
    "distance-walking-running",
    "flights-climbed",
    "apple-exercise-time",
    "apple-stand-time",
}

# Metrics where there is typically one sample per day — take mean (or first).
SINGLE_VALUE_METRICS = {
    "resting-heart-rate",
    "walking-heart-rate-average",
}

# Multi-sample metrics — aggregate by daily mean.
MEAN_METRICS = {
    "heart-rate-variability-sdnn",
    "walking-speed",
    "walking-step-length",
    "respiratory-rate",
    "oxygen-saturation",
    "blood-pressure-systolic",
    "blood-pressure-diastolic",
    "heart-rate",
}

# Common IANA timezone offsets (hours from UTC).
# Only commonly encountered zones are listed; extend as needed.
TIMEZONE_OFFSETS = {
    "Asia/Shanghai": 8,
    "Asia/Hong_Kong": 8,
    "Asia/Taipei": 8,
    "Asia/Tokyo": 9,
    "Asia/Seoul": 9,
    "Asia/Singapore": 8,
    "Asia/Kolkata": 5.5,
    "Asia/Dubai": 4,
    "Europe/London": 0,
    "Europe/Paris": 1,
    "Europe/Berlin": 1,
    "Europe/Moscow": 3,
    "America/New_York": -5,
    "America/Chicago": -6,
    "America/Denver": -7,
    "America/Los_Angeles": -8,
    "America/Anchorage": -9,
    "Pacific/Honolulu": -10,
    "Australia/Sydney": 11,
    "Australia/Melbourne": 11,
    "Pacific/Auckland": 13,
    "UTC": 0,
}

# Key metrics used by scan mode for trend/anomaly detection.
SCAN_METRICS = [
    ("step-count", "sum"),
    ("resting-heart-rate", "mean"),
    ("heart-rate-variability-sdnn", "mean"),
    ("active-energy-burned", "sum"),
    ("apple-exercise-time", "sum"),
]

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _listdir_sorted(path):
    """List directory entries sorted, returning empty list if path is missing."""
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def _parse_iso_datetime(s):
    """Parse an ISO-8601 datetime string to a datetime object (UTC).

    Handles both 'Z' suffix and '+00:00' offsets. Microseconds are optional.
    """
    s = s.replace("Z", "+00:00")
    # Python 3.9 does not support datetime.fromisoformat with 'Z', but does
    # handle '+00:00' on the basic format.
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        # Fallback: strip fractional seconds and retry
        if "." in s:
            base, rest = s.split(".", 1)
            # rest might be e.g. "288Z" or "288+00:00"
            offset_part = ""
            for sep in ("+", "-"):
                idx = rest.find(sep)
                if idx != -1:
                    offset_part = rest[idx:]
                    break
            return datetime.fromisoformat(base + offset_part)
        raise


def _utc_to_local_str(utc_str, tz_name):
    """Convert a UTC ISO datetime string to a local time string.

    Uses zoneinfo (Python 3.9+) for DST-aware conversion when available,
    falling back to the static TIMEZONE_OFFSETS lookup otherwise.
    Returns ISO format string in local time (no tzinfo suffix).
    """
    dt = _parse_iso_datetime(utc_str)
    if _HAS_ZONEINFO and tz_name:
        try:
            # Ensure dt is UTC-aware for proper conversion
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            local_dt = dt.astimezone(ZoneInfo(tz_name))
            return local_dt.strftime("%Y-%m-%dT%H:%M:%S")
        except (KeyError, ValueError):
            pass  # Unknown tz_name — fall through to static lookup
    offset_hours = TIMEZONE_OFFSETS.get(tz_name, 0)
    local_dt = dt + timedelta(hours=offset_hours)
    return local_dt.strftime("%Y-%m-%dT%H:%M:%S")


def _date_range(from_date, to_date):
    """Yield date objects from from_date to to_date inclusive."""
    d = from_date
    while d <= to_date:
        yield d
        d += timedelta(days=1)


def _iso_to_date(s):
    """Parse 'YYYY-MM-DD' to a date object."""
    parts = s.split("-")
    return date(int(parts[0]), int(parts[1]), int(parts[2]))


def _safe_round(val, decimals=2):
    """Round a value, returning None if val is None."""
    if val is None:
        return None
    return round(val, decimals)


# ---------------------------------------------------------------------------
# Data loading layer
# ---------------------------------------------------------------------------


def load_metric(data_dir, metric, from_date, to_date):
    """Load raw metric data from the directory tree.

    Args:
        data_dir: Root data directory (contains YYYY/MM/DD/*.json).
        metric: Metric file stem, e.g. 'step-count'.
        from_date: Start date (date object), inclusive.
        to_date: End date (date object), inclusive.

    Returns:
        List of dicts: [{"date": date_obj, "samples": [...], "timezone": str|None}, ...]
        Only days where the file exists and has valid JSON are included.
    """
    results = []
    for d in _date_range(from_date, to_date):
        day_dir = os.path.join(
            data_dir,
            f"{d.year:04d}",
            f"{d.month:02d}",
            f"{d.day:02d}",
        )
        filepath = os.path.join(day_dir, f"{metric}.json")
        if not os.path.isfile(filepath):
            continue
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        samples = data.get("samples")
        if not isinstance(samples, list):
            continue
        tz = data.get("timezone")
        results.append({"date": d, "samples": samples, "timezone": tz})
    return results


def dedup_samples(samples):
    """Deduplicate additive-metric samples: prefer Watch over other sources.

    Algorithm:
        1. Separate into Watch samples and non-Watch samples.
        2. Sort Watch samples by start time.
        3. For each non-Watch sample, check overlap with any Watch interval.
           If overlap exists, drop it. Otherwise keep it.
        4. Return Watch samples + surviving non-Watch samples.
    """
    watch_samples = []
    other_samples = []

    for s in samples:
        device = s.get("device", "")
        if "Watch" in device:
            watch_samples.append(s)
        else:
            other_samples.append(s)

    if not watch_samples:
        # No watch data — keep everything.
        return samples

    # Parse Watch intervals and sort by start.
    watch_intervals = []
    for s in watch_samples:
        try:
            start = _parse_iso_datetime(s["start"])
            end = _parse_iso_datetime(s["end"])
            watch_intervals.append((start, end))
        except (KeyError, ValueError):
            watch_intervals.append(None)
    # Filter out parse failures and sort.
    watch_intervals = sorted(
        [iv for iv in watch_intervals if iv is not None], key=lambda x: x[0]
    )

    # Keep non-Watch samples that do NOT overlap any Watch interval.
    kept = list(watch_samples)
    for s in other_samples:
        try:
            s_start = _parse_iso_datetime(s["start"])
            s_end = _parse_iso_datetime(s["end"])
        except (KeyError, ValueError):
            kept.append(s)  # Can't parse — keep it.
            continue
        overlaps = False
        for w_start, w_end in watch_intervals:
            # Overlap if s_start < w_end and s_end > w_start
            if s_start < w_end and s_end > w_start:
                overlaps = True
                break
        if not overlaps:
            kept.append(s)

    return kept


def aggregate_sum(data_dir, metric, from_date, to_date):
    """Aggregate a metric by summing sample values per day (with dedup).

    Returns: OrderedDict {date_obj: total_value}
    """
    raw = load_metric(data_dir, metric, from_date, to_date)
    result = OrderedDict()
    for entry in raw:
        d = entry["date"]
        samples = dedup_samples(entry["samples"])
        total = 0.0
        for s in samples:
            val = s.get("value")
            if val is not None:
                try:
                    total += float(val)
                except (ValueError, TypeError):
                    pass
        result[d] = total
    return result


def aggregate_mean(data_dir, metric, from_date, to_date):
    """Aggregate a metric by averaging sample values per day (no dedup).

    Returns: OrderedDict {date_obj: mean_value}
    """
    raw = load_metric(data_dir, metric, from_date, to_date)
    result = OrderedDict()
    for entry in raw:
        d = entry["date"]
        values = []
        for s in entry["samples"]:
            val = s.get("value")
            if val is not None:
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    pass
        if values:
            result[d] = sum(values) / len(values)
    return result


def aggregate_single(data_dir, metric, from_date, to_date):
    """Aggregate a metric that has ~1 sample/day, taking the mean.

    Functionally identical to aggregate_mean but semantically distinct.
    Returns: OrderedDict {date_obj: value}
    """
    return aggregate_mean(data_dir, metric, from_date, to_date)


def aggregate_metric(data_dir, metric, from_date, to_date):
    """Auto-select aggregation strategy based on metric name.

    Returns: OrderedDict {date_obj: value}
    """
    if metric in ADDITIVE_METRICS:
        return aggregate_sum(data_dir, metric, from_date, to_date)
    elif metric in SINGLE_VALUE_METRICS:
        return aggregate_single(data_dir, metric, from_date, to_date)
    else:
        return aggregate_mean(data_dir, metric, from_date, to_date)


# ---------------------------------------------------------------------------
# Statistics helpers (stdlib only)
# ---------------------------------------------------------------------------


def _mean(values):
    """Compute the mean of a list of numbers. Returns None if empty."""
    if not values:
        return None
    return sum(values) / len(values)


def _stdev(values):
    """Compute population standard deviation. Returns None if < 2 values."""
    if len(values) < 2:
        return None
    m = sum(values) / len(values)
    variance = sum((x - m) ** 2 for x in values) / len(values)
    return variance ** 0.5


def _cv(values):
    """Coefficient of variation (stdev / mean). Returns None if mean is 0."""
    m = _mean(values)
    s = _stdev(values)
    if m is None or s is None or m == 0:
        return None
    return s / m


def _median(values):
    """Median value. Returns None if empty."""
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


def _percentiles(values):
    """P10, P25, P75, P90. Returns None if empty."""
    if not values:
        return None
    s = sorted(values)
    n = len(s)

    def _lerp(p):
        k = (n - 1) * p
        f = int(k)
        c = f + 1
        if c >= n:
            return s[f]
        return s[f] + (k - f) * (s[c] - s[f])

    return {
        "p10": round(_lerp(0.10), 2),
        "p25": round(_lerp(0.25), 2),
        "p75": round(_lerp(0.75), 2),
        "p90": round(_lerp(0.90), 2),
    }


def _min_with_date(dated_dict):
    """Min value with its date from an OrderedDict{date: value}. Returns None if empty."""
    if not dated_dict:
        return None
    d, v = min(dated_dict.items(), key=lambda x: x[1])
    return {"value": v, "date": str(d)}


def _max_with_date(dated_dict):
    """Max value with its date from an OrderedDict{date: value}. Returns None if empty."""
    if not dated_dict:
        return None
    d, v = max(dated_dict.items(), key=lambda x: x[1])
    return {"value": v, "date": str(d)}


def _rolling_avg(values, window=7):
    """Rolling average. Returns list same length as values; None for positions with insufficient data."""
    result = []
    for i in range(len(values)):
        if i < window - 1:
            result.append(None)
        else:
            chunk = values[i - window + 1 : i + 1]
            result.append(round(sum(chunk) / len(chunk), 2))
    return result


def _linear_regression(values):
    """Simple linear regression (y = slope*x + intercept). Returns (slope, intercept) or None."""
    n = len(values)
    if n < 2:
        return None
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    if den == 0:
        return (0.0, y_mean)
    slope = num / den
    intercept = y_mean - slope * x_mean
    return (round(slope, 6), round(intercept, 6))


_DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _day_of_week_avg(dated_dict):
    """Average per day of week from OrderedDict{date: value}. Returns dict with Mon-Sun keys."""
    buckets = {d: [] for d in _DOW_NAMES}
    for dt, val in dated_dict.items():
        buckets[_DOW_NAMES[dt.weekday()]].append(val)
    return {d: round(sum(v) / len(v), 2) if v else None for d, v in buckets.items()}


def _distribution_bins(values, n_bins=10):
    """Histogram bins. Returns list of {from, to, count} or None if empty."""
    if not values:
        return None
    lo, hi = min(values), max(values)
    if lo == hi:
        return [{"from": round(lo, 2), "to": round(hi, 2), "count": len(values)}]
    width = (hi - lo) / n_bins
    bins = []
    for i in range(n_bins):
        b_from = lo + i * width
        b_to = lo + (i + 1) * width
        count = sum(1 for v in values if (b_from <= v < b_to) or (i == n_bins - 1 and v == b_to))
        bins.append({"from": round(b_from, 2), "to": round(b_to, 2), "count": count})
    return bins


def _longest_streak(dated_dict, threshold):
    """Longest consecutive-day streak where value >= threshold. Returns int."""
    if not dated_dict:
        return 0
    dates = sorted(dated_dict.keys())
    best = 0
    current = 0
    prev = None
    for d in dates:
        if dated_dict[d] >= threshold:
            if prev and (d - prev).days == 1:
                current += 1
            else:
                current = 1
        else:
            current = 0
        best = max(best, current)
        prev = d
    return best


def _build_metric_stats(dated_dict):
    """Build comprehensive stats for a single metric from OrderedDict{date: value}.

    Returns a dict with: mean, median, stdev, cv, percentiles, min, max,
    n, dates, values, rolling_7d, rolling_30d, trend_slope, trend_direction,
    day_of_week, distribution, period_comparison.
    """
    dates = list(dated_dict.keys())
    values = list(dated_dict.values())
    n = len(values)

    if n == 0:
        return {
            "n": 0, "mean": None, "median": None, "stdev": None, "cv": None,
            "percentiles": None, "min": None, "max": None,
            "dates": [], "values": [],
            "rolling_7d": [], "rolling_30d": [],
            "trend_slope": None, "trend_direction": None,
            "day_of_week": {d: None for d in _DOW_NAMES},
            "distribution": None, "period_comparison": None,
        }

    mean_val = _mean(values)
    stdev_val = _stdev(values)
    reg = _linear_regression(values)
    slope = reg[0] if reg else None

    if slope is None or mean_val is None or mean_val == 0:
        direction = "flat"
    elif abs(slope * n) / abs(mean_val) > 0.05:
        direction = "up" if slope > 0 else "down"
    else:
        direction = "flat"

    # Period-over-period: split in half, compare
    period_comparison = None
    if n >= 4:
        mid = n // 2
        first_half = values[:mid]
        second_half = values[mid:]
        fh_avg = _mean(first_half)
        sh_avg = _mean(second_half)
        if fh_avg and fh_avg != 0:
            change_pct = round((sh_avg - fh_avg) / abs(fh_avg) * 100, 1)
        else:
            change_pct = 0.0
        period_comparison = {
            "first_half_avg": _safe_round(fh_avg),
            "second_half_avg": _safe_round(sh_avg),
            "change_pct": change_pct,
        }

    return {
        "n": n,
        "mean": _safe_round(mean_val),
        "median": _safe_round(_median(values)),
        "stdev": _safe_round(stdev_val),
        "cv": _safe_round(_cv(values)),
        "percentiles": _percentiles(values),
        "min": _min_with_date(dated_dict),
        "max": _max_with_date(dated_dict),
        "dates": [str(d) for d in dates],
        "values": [_safe_round(v) for v in values],
        "rolling_7d": _rolling_avg(values, 7),
        "rolling_30d": _rolling_avg(values, 30),
        "trend_slope": _safe_round(slope, 4) if slope is not None else None,
        "trend_direction": direction,
        "day_of_week": _day_of_week_avg(dated_dict),
        "distribution": _distribution_bins(values, n_bins=10),
        "period_comparison": period_comparison,
    }


def pearson(x, y):
    """Compute Pearson correlation coefficient with approximate p-value.

    Args:
        x, y: Lists of numbers of equal length.

    Returns:
        (r, p, n) tuple.
    """
    n = len(x)
    if n < 7:
        return 0.0, 1.0, n
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y)) / n
    std_x = (sum((xi - mean_x) ** 2 for xi in x) / n) ** 0.5
    std_y = (sum((yi - mean_y) ** 2 for yi in y) / n) ** 0.5
    if std_x == 0 or std_y == 0:
        return 0.0, 1.0, n
    r = cov / (std_x * std_y)
    # Clamp r to [-1, 1] for numerical safety.
    r = max(-1.0, min(1.0, r))
    if abs(r) >= 1.0:
        return round(r, 4), 0.0, n
    # Approximate p-value via t-distribution.
    t_stat = r * ((n - 2) / (1 - r ** 2)) ** 0.5
    if abs(t_stat) < 6:
        p = math.exp(-0.717 * abs(t_stat) - 0.416 * t_stat ** 2)
    else:
        p = 0.0
    return round(r, 4), round(p, 4), n


# ---------------------------------------------------------------------------
# Sleep analysis helpers
# ---------------------------------------------------------------------------

SLEEP_STAGES = {"asleepCore", "asleepDeep", "asleepREM"}


def _analyze_sleep_day(samples, tz_name):
    """Analyze one day's sleep-analysis samples.

    Returns a dict with total_hrs, deep_pct, core_pct, rem_pct, awake_min,
    bedtime_local, waketime_local — or None if no valid sleep data.
    """
    stage_minutes = {"asleepCore": 0.0, "asleepDeep": 0.0, "asleepREM": 0.0}
    awake_minutes = 0.0
    sleep_starts = []  # start times of non-awake samples
    sleep_ends = []    # end times of non-awake samples

    for s in samples:
        val = s.get("value", "")
        try:
            start_dt = _parse_iso_datetime(s["start"])
            end_dt = _parse_iso_datetime(s["end"])
        except (KeyError, ValueError):
            continue

        duration_min = (end_dt - start_dt).total_seconds() / 60.0
        if duration_min <= 0:
            continue

        if val in SLEEP_STAGES:
            stage_minutes[val] += duration_min
            sleep_starts.append(s["start"])
            sleep_ends.append(s["end"])
        elif val == "awake":
            awake_minutes += duration_min

    total_sleep_min = sum(stage_minutes.values())
    if total_sleep_min == 0:
        return None

    total_hrs = total_sleep_min / 60.0

    result = {
        "total_hrs": round(total_hrs, 2),
        "deep_pct": round(stage_minutes["asleepDeep"] / total_sleep_min * 100, 1),
        "core_pct": round(stage_minutes["asleepCore"] / total_sleep_min * 100, 1),
        "rem_pct": round(stage_minutes["asleepREM"] / total_sleep_min * 100, 1),
        "awake_min": round(awake_minutes, 1),
    }

    # Bedtime = earliest start of a non-awake sample, converted to local.
    if sleep_starts:
        earliest = min(sleep_starts, key=lambda s: _parse_iso_datetime(s))
        result["bedtime_local"] = _utc_to_local_str(earliest, tz_name or "UTC")

    # Waketime = latest end of a non-awake sample, converted to local.
    if sleep_ends:
        latest = max(sleep_ends, key=lambda s: _parse_iso_datetime(s))
        result["waketime_local"] = _utc_to_local_str(latest, tz_name or "UTC")

    return result


# ---------------------------------------------------------------------------
# Analysis modes
# ---------------------------------------------------------------------------


def mode_scan(data_dir, from_date, to_date):
    """Quick overview: trend alerts, anomalies, correlations, consistency.

    Splits the period in half, compares averages for key metrics.
    Detects Z-score anomalies and computes top pairwise correlations.
    """
    midpoint = from_date + (to_date - from_date) // 2
    half1_end = midpoint
    half2_start = midpoint + timedelta(days=1)

    trend_alerts = []
    anomalies = []
    all_daily = {}  # metric_name -> {date: value}

    # Aggregate key metrics and detect trends + anomalies.
    for metric_name, agg_type in SCAN_METRICS:
        daily = aggregate_metric(data_dir, metric_name, from_date, to_date)
        if not daily:
            continue

        all_daily[metric_name] = daily

        values = list(daily.values())
        m = _mean(values)
        s = _stdev(values)

        # Trend detection: compare first half vs second half.
        h1_vals = [v for d, v in daily.items() if d <= half1_end]
        h2_vals = [v for d, v in daily.items() if d >= half2_start]
        h1_avg = _mean(h1_vals)
        h2_avg = _mean(h2_vals)

        if h1_avg is not None and h2_avg is not None and h1_avg != 0:
            change_pct = (h2_avg - h1_avg) / abs(h1_avg) * 100
            if abs(change_pct) > 15:
                direction = "up" if change_pct > 0 else "down"
                trend_alerts.append({
                    "metric": metric_name,
                    "direction": direction,
                    "change_pct": round(change_pct, 1),
                    "first_half_avg": _safe_round(h1_avg),
                    "second_half_avg": _safe_round(h2_avg),
                })

        # Anomaly detection: Z-score > 2.0 or < -2.0.
        if m is not None and s is not None and s > 0:
            for d, v in daily.items():
                z = (v - m) / s
                if abs(z) > 2.0:
                    anomalies.append({
                        "metric": metric_name,
                        "date": d.isoformat(),
                        "value": _safe_round(v),
                        "z_score": round(z, 2),
                    })

    # Also load sleep for correlations and consistency.
    sleep_data = load_metric(data_dir, "sleep-analysis", from_date, to_date)
    sleep_daily = {}
    bedtimes_min = []  # bedtime as minutes-from-midnight for stdev calc
    for entry in sleep_data:
        analysis = _analyze_sleep_day(entry["samples"], entry.get("timezone"))
        if analysis:
            sleep_daily[entry["date"]] = analysis["total_hrs"]
            if "bedtime_local" in analysis:
                bt = _parse_iso_datetime(analysis["bedtime_local"])
                # Minutes from midnight (allow negative for before midnight).
                mins = bt.hour * 60 + bt.minute
                if mins < 720:  # Before noon = early morning, add 24h offset
                    mins += 1440
                bedtimes_min.append(mins)
    if sleep_daily:
        all_daily["sleep-hours"] = {d: v for d, v in sleep_daily.items()}

    # Cross-metric correlations (top 10 by |r|).
    correlations = []
    metric_names = list(all_daily.keys())
    for i in range(len(metric_names)):
        for j in range(i + 1, len(metric_names)):
            name_a = metric_names[i]
            name_b = metric_names[j]
            daily_a = all_daily[name_a]
            daily_b = all_daily[name_b]
            for lag in [0, 1, 2]:
                x_vals = []
                y_vals = []
                for d in sorted(daily_a.keys()):
                    d_shifted = d + timedelta(days=lag)
                    if d in daily_a and d_shifted in daily_b:
                        x_vals.append(daily_a[d])
                        y_vals.append(daily_b[d_shifted])
                if len(x_vals) >= 7:
                    r, p, n = pearson(x_vals, y_vals)
                    if abs(r) > 0.2:
                        correlations.append({
                            "metric_a": name_a,
                            "metric_b": name_b,
                            "lag": lag,
                            "r": r,
                            "p": p,
                            "n": n,
                        })

    # Sort by |r| descending, keep top 10.
    correlations.sort(key=lambda c: abs(c["r"]), reverse=True)
    correlations = correlations[:10]

    # Consistency metrics.
    consistency = {}

    # Bedtime stdev (in minutes).
    if len(bedtimes_min) >= 2:
        bt_std = _stdev(bedtimes_min)
        consistency["bedtime_stdev_min"] = _safe_round(bt_std, 1)

    # Exercise frequency (days with exercise > 0 / total days).
    exercise_daily = aggregate_metric(data_dir, "apple-exercise-time", from_date, to_date)
    if exercise_daily:
        days_with_exercise = sum(1 for v in exercise_daily.values() if v > 0)
        total_days = (to_date - from_date).days + 1
        consistency["exercise_frequency"] = round(days_with_exercise / total_days, 2)

    # Step CV.
    step_daily = all_daily.get("step-count", {})
    if step_daily:
        step_cv = _cv(list(step_daily.values()))
        if step_cv is not None:
            consistency["step_cv"] = round(step_cv, 3)

    return {
        "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "trend_alerts": trend_alerts,
        "anomalies": anomalies,
        "correlations": correlations,
        "consistency": consistency,
    }


def mode_sleep(data_dir, from_date, to_date):
    """Sleep deep-dive: nightly totals, stages, bedtime, consistency."""
    raw = load_metric(data_dir, "sleep-analysis", from_date, to_date)
    nightly = []

    for entry in raw:
        analysis = _analyze_sleep_day(entry["samples"], entry.get("timezone"))
        if analysis:
            record = {"date": entry["date"].isoformat()}
            record.update(analysis)
            nightly.append(record)

    # Compute averages.
    averages = {}
    if nightly:
        for key in ["total_hrs", "deep_pct", "core_pct", "rem_pct", "awake_min"]:
            vals = [n[key] for n in nightly if key in n]
            if vals:
                averages[key] = _safe_round(_mean(vals))

    return {
        "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "nightly": nightly,
        "averages": averages,
        "nights_analyzed": len(nightly),
    }


def mode_activity(data_dir, from_date, to_date):
    """Activity analysis: steps, active calories, exercise, distance."""
    steps = aggregate_metric(data_dir, "step-count", from_date, to_date)
    active_kcal = aggregate_metric(data_dir, "active-energy-burned", from_date, to_date)
    exercise_min = aggregate_metric(data_dir, "apple-exercise-time", from_date, to_date)
    distance = aggregate_metric(data_dir, "distance-walking-running", from_date, to_date)

    # Collect all dates across metrics.
    all_dates = sorted(set(
        list(steps.keys()) +
        list(active_kcal.keys()) +
        list(exercise_min.keys()) +
        list(distance.keys())
    ))

    daily = []
    for d in all_dates:
        daily.append({
            "date": d.isoformat(),
            "steps": _safe_round(steps.get(d, 0), 0),
            "active_kcal": _safe_round(active_kcal.get(d, 0)),
            "exercise_min": _safe_round(exercise_min.get(d, 0), 1),
            "distance_km": _safe_round(distance.get(d, 0), 2),
        })

    # Averages.
    averages = {}
    for key, data_dict in [("steps", steps), ("active_kcal", active_kcal),
                            ("exercise_min", exercise_min), ("distance_km", distance)]:
        vals = list(data_dict.values())
        if vals:
            averages[key] = _safe_round(_mean(vals))

    return {
        "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "daily": daily,
        "averages": averages,
        "days_analyzed": len(daily),
    }


def mode_heart(data_dir, from_date, to_date):
    """Heart analysis: weekly resting HR, weekly HRV, walking HR trends."""
    rhr = aggregate_metric(data_dir, "resting-heart-rate", from_date, to_date)
    hrv = aggregate_metric(data_dir, "heart-rate-variability-sdnn", from_date, to_date)
    whr = aggregate_metric(data_dir, "walking-heart-rate-average", from_date, to_date)

    def _weekly_averages(daily_dict):
        """Group daily values into ISO weeks and average each."""
        weeks = {}
        for d, v in daily_dict.items():
            # ISO week: (year, week_number)
            iso_year, iso_week, _ = d.isocalendar()
            key = f"{iso_year}-W{iso_week:02d}"
            if key not in weeks:
                weeks[key] = []
            weeks[key].append(v)
        result = []
        for week_key in sorted(weeks.keys()):
            vals = weeks[week_key]
            result.append({
                "week": week_key,
                "avg": _safe_round(_mean(vals)),
                "n": len(vals),
            })
        return result

    result = {
        "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "weekly_resting_hr": _weekly_averages(rhr),
        "weekly_hrv": _weekly_averages(hrv),
    }

    # Walking HR overall average.
    whr_vals = list(whr.values())
    if whr_vals:
        result["avg_walking_hr"] = _safe_round(_mean(whr_vals))

    # Overall summaries.
    rhr_vals = list(rhr.values())
    hrv_vals = list(hrv.values())
    if rhr_vals:
        result["avg_resting_hr"] = _safe_round(_mean(rhr_vals))
    if hrv_vals:
        result["avg_hrv"] = _safe_round(_mean(hrv_vals))

    return result


def mode_correlate(data_dir, from_date, to_date, target, lags):
    """Cross-metric correlation with time lag.

    Correlates all available metrics against the target metric at specified lags.
    """
    # Discover available metrics by checking a sample of days.
    available = _discover_metrics(data_dir, from_date, to_date)
    if target not in available:
        return {"error": f"Target metric '{target}' not found in data"}

    target_daily = aggregate_metric(data_dir, target, from_date, to_date)
    if len(target_daily) < 7:
        return {"error": f"Not enough data for '{target}' (need >= 7 days, got {len(target_daily)})"}

    correlations = []
    for metric in available:
        if metric == target:
            continue
        other_daily = aggregate_metric(data_dir, metric, from_date, to_date)
        if len(other_daily) < 7:
            continue

        for lag in lags:
            x_vals = []
            y_vals = []
            for d in sorted(target_daily.keys()):
                d_shifted = d + timedelta(days=lag)
                if d in target_daily and d_shifted in other_daily:
                    x_vals.append(target_daily[d])
                    y_vals.append(other_daily[d_shifted])
            if len(x_vals) >= 7:
                r, p, n = pearson(x_vals, y_vals)
                correlations.append({
                    "metric_a": target,
                    "metric_b": metric,
                    "lag": lag,
                    "r": r,
                    "p": p,
                    "n": n,
                })

    correlations.sort(key=lambda c: abs(c["r"]), reverse=True)

    return {
        "period": {"from": from_date.isoformat(), "to": to_date.isoformat()},
        "target": target,
        "lags": lags,
        "correlations": correlations,
    }


def _discover_metrics(data_dir, from_date, to_date):
    """Discover which metric files exist in the date range.

    Samples up to 10 evenly-spaced days to find metric filenames.
    """
    total_days = (to_date - from_date).days + 1
    if total_days <= 10:
        sample_dates = list(_date_range(from_date, to_date))
    else:
        step = total_days // 10
        sample_dates = [from_date + timedelta(days=i * step) for i in range(10)]
        sample_dates.append(to_date)

    found = set()
    for d in sample_dates:
        day_dir = os.path.join(
            data_dir,
            f"{d.year:04d}",
            f"{d.month:02d}",
            f"{d.day:02d}",
        )
        if not os.path.isdir(day_dir):
            continue
        for fname in os.listdir(day_dir):
            if fname.endswith(".json") and not fname.startswith("workout-"):
                found.add(fname[:-5])

    return sorted(found)


def mode_compare(data_dir, p1_str, p2_str):
    """Two-period side-by-side comparison.

    p1_str, p2_str: 'YYYY-MM' month strings.
    """
    def _month_range(ym_str):
        parts = ym_str.split("-")
        y, m = int(parts[0]), int(parts[1])
        first = date(y, m, 1)
        # Last day of month.
        if m == 12:
            last = date(y + 1, 1, 1) - timedelta(days=1)
        else:
            last = date(y, m + 1, 1) - timedelta(days=1)
        return first, last

    p1_start, p1_end = _month_range(p1_str)
    p2_start, p2_end = _month_range(p2_str)

    # Discover metrics from both periods.
    metrics_p1 = set(_discover_metrics(data_dir, p1_start, p1_end))
    metrics_p2 = set(_discover_metrics(data_dir, p2_start, p2_end))
    common_metrics = sorted(metrics_p1 & metrics_p2)

    comparisons = []
    for metric in common_metrics:
        d1 = aggregate_metric(data_dir, metric, p1_start, p1_end)
        d2 = aggregate_metric(data_dir, metric, p2_start, p2_end)
        v1 = list(d1.values())
        v2 = list(d2.values())
        if not v1 or not v2:
            continue
        avg1 = _mean(v1)
        avg2 = _mean(v2)
        delta = avg2 - avg1
        delta_pct = (delta / abs(avg1) * 100) if avg1 != 0 else None

        comparisons.append({
            "name": metric,
            "p1_avg": _safe_round(avg1),
            "p2_avg": _safe_round(avg2),
            "delta": _safe_round(delta),
            "delta_pct": _safe_round(delta_pct, 1),
            "p1_days": len(v1),
            "p2_days": len(v2),
        })

    return {
        "p1": p1_str,
        "p2": p2_str,
        "metrics": comparisons,
    }


def mode_yearly(data_dir, year):
    """12-month annual summary.

    For each month: avg steps, avg sleep hrs, avg resting HR, avg HRV,
    total exercise min, total active kcal.
    Also: bests and worsts for the year.
    """
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    # Load full-year daily data for key metrics.
    steps = aggregate_metric(data_dir, "step-count", year_start, year_end)
    active_kcal = aggregate_metric(data_dir, "active-energy-burned", year_start, year_end)
    exercise = aggregate_metric(data_dir, "apple-exercise-time", year_start, year_end)
    rhr = aggregate_metric(data_dir, "resting-heart-rate", year_start, year_end)
    hrv = aggregate_metric(data_dir, "heart-rate-variability-sdnn", year_start, year_end)

    # Sleep totals per day.
    sleep_data = load_metric(data_dir, "sleep-analysis", year_start, year_end)
    sleep_daily = {}
    for entry in sleep_data:
        analysis = _analyze_sleep_day(entry["samples"], entry.get("timezone"))
        if analysis:
            sleep_daily[entry["date"]] = analysis["total_hrs"]

    # Monthly breakdown.
    monthly = []
    for m in range(1, 13):
        m_start = date(year, m, 1)
        if m == 12:
            m_end = date(year, 12, 31)
        else:
            m_end = date(year, m + 1, 1) - timedelta(days=1)

        def _month_values(daily_dict):
            return [v for d, v in daily_dict.items() if m_start <= d <= m_end]

        s_vals = _month_values(steps)
        ak_vals = _month_values(active_kcal)
        ex_vals = _month_values(exercise)
        rhr_vals = _month_values(rhr)
        hrv_vals = _month_values(hrv)
        sl_vals = _month_values(sleep_daily)

        monthly.append({
            "month": f"{year}-{m:02d}",
            "steps_avg": _safe_round(_mean(s_vals), 0) if s_vals else None,
            "sleep_avg_hrs": _safe_round(_mean(sl_vals)) if sl_vals else None,
            "resting_hr_avg": _safe_round(_mean(rhr_vals)) if rhr_vals else None,
            "hrv_avg": _safe_round(_mean(hrv_vals)) if hrv_vals else None,
            "exercise_total_min": _safe_round(sum(ex_vals), 0) if ex_vals else None,
            "active_kcal_total": _safe_round(sum(ak_vals), 0) if ak_vals else None,
            "days_with_data": len(s_vals),
        })

    # Bests and worsts.
    bests = {}
    worsts = {}

    if steps:
        best_step_day = max(steps.items(), key=lambda x: x[1])
        worst_step_day = min(steps.items(), key=lambda x: x[1])
        bests["highest_step_day"] = {
            "date": best_step_day[0].isoformat(),
            "value": _safe_round(best_step_day[1], 0),
        }
        worsts["lowest_step_day"] = {
            "date": worst_step_day[0].isoformat(),
            "value": _safe_round(worst_step_day[1], 0),
        }

    if sleep_daily:
        best_sleep = max(sleep_daily.items(), key=lambda x: x[1])
        worst_sleep = min(sleep_daily.items(), key=lambda x: x[1])
        bests["longest_sleep"] = {
            "date": best_sleep[0].isoformat(),
            "value": _safe_round(best_sleep[1]),
        }
        worsts["shortest_sleep"] = {
            "date": worst_sleep[0].isoformat(),
            "value": _safe_round(worst_sleep[1]),
        }

    if rhr:
        best_rhr = min(rhr.items(), key=lambda x: x[1])  # Lower is better
        worst_rhr = max(rhr.items(), key=lambda x: x[1])
        bests["lowest_resting_hr"] = {
            "date": best_rhr[0].isoformat(),
            "value": _safe_round(best_rhr[1]),
        }
        worsts["highest_resting_hr"] = {
            "date": worst_rhr[0].isoformat(),
            "value": _safe_round(worst_rhr[1]),
        }

    if hrv:
        best_hrv = max(hrv.items(), key=lambda x: x[1])  # Higher is better
        bests["highest_hrv"] = {
            "date": best_hrv[0].isoformat(),
            "value": _safe_round(best_hrv[1]),
        }

    return {
        "year": year,
        "monthly": monthly,
        "bests": bests,
        "worsts": worsts,
    }


# ---------------------------------------------------------------------------
# Date range resolution
# ---------------------------------------------------------------------------


def _resolve_dates(args, data_dir):
    """Resolve --from/--to/--period into (from_date, to_date).

    If neither --from nor --period is given, defaults to last 30 days
    from the latest data found.
    """
    if args.get("from_date") and args.get("to_date"):
        return _iso_to_date(args["from_date"]), _iso_to_date(args["to_date"])

    if args.get("from_date") and not args.get("to_date"):
        return _iso_to_date(args["from_date"]), date.today()

    # Determine the latest date with data.
    latest = _find_latest_date(data_dir)
    if latest is None:
        latest = date.today()

    period_str = args.get("period", "30d")
    days = _parse_period(period_str)

    to_date = latest
    if args.get("to_date"):
        to_date = _iso_to_date(args["to_date"])

    from_date = to_date - timedelta(days=days - 1)
    return from_date, to_date


def _parse_period(s):
    """Parse a period string like '30d' or '90d' into number of days."""
    s = s.strip().lower()
    if s.endswith("d"):
        try:
            return int(s[:-1])
        except ValueError:
            pass
    # Default to 30 days.
    return 30


def _find_latest_date(data_dir):
    """Find the latest date with data in the directory tree."""
    latest = None
    for year_name in _listdir_sorted(data_dir):
        if not (len(year_name) == 4 and year_name.isdigit()):
            continue
        year_path = os.path.join(data_dir, year_name)
        if not os.path.isdir(year_path):
            continue
        for month_name in _listdir_sorted(year_path):
            if not (len(month_name) == 2 and month_name.isdigit()):
                continue
            month_path = os.path.join(year_path, month_name)
            if not os.path.isdir(month_path):
                continue
            for day_name in _listdir_sorted(month_path):
                if not (len(day_name) == 2 and day_name.isdigit()):
                    continue
                day_path = os.path.join(month_path, day_name)
                if not os.path.isdir(day_path):
                    continue
                try:
                    d = date(int(year_name), int(month_name), int(day_name))
                except ValueError:
                    continue
                if latest is None or d > latest:
                    latest = d
    return latest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Apple Health data in MyLifeDB format.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("data_dir", help="Path to the data directory (YYYY/MM/DD/*.json)")
    parser.add_argument("--mode", required=True,
                        choices=["scan", "sleep", "activity", "heart",
                                 "correlate", "compare", "yearly"],
                        help="Analysis mode")
    parser.add_argument("--from", dest="from_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="to_date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--period", default="30d",
                        help="Alternative to --from/--to: last N days (e.g. 30d)")
    parser.add_argument("--target", help="For correlate mode: target metric name")
    parser.add_argument("--lag", default="0,1,2,3",
                        help="For correlate mode: comma-separated lag days")
    parser.add_argument("--p1", help="For compare mode: first period (YYYY-MM)")
    parser.add_argument("--p2", help="For compare mode: second period (YYYY-MM)")
    parser.add_argument("--year", type=int, help="For yearly mode: year (YYYY)")

    args = parser.parse_args()
    data_dir = os.path.abspath(args.data_dir)

    if not os.path.isdir(data_dir):
        print(json.dumps({"error": f"Not a directory: {data_dir}"}))
        sys.exit(1)

    mode = args.mode

    try:
        if mode == "compare":
            if not args.p1 or not args.p2:
                print(json.dumps({"error": "compare mode requires --p1 and --p2 (YYYY-MM)"}))
                sys.exit(1)
            result = mode_compare(data_dir, args.p1, args.p2)

        elif mode == "yearly":
            if not args.year:
                print(json.dumps({"error": "yearly mode requires --year (YYYY)"}))
                sys.exit(1)
            result = mode_yearly(data_dir, args.year)

        elif mode == "correlate":
            if not args.target:
                print(json.dumps({"error": "correlate mode requires --target metric"}))
                sys.exit(1)
            from_date, to_date = _resolve_dates(vars(args), data_dir)
            lags = [int(x.strip()) for x in args.lag.split(",")]
            result = mode_correlate(data_dir, from_date, to_date, args.target, lags)

        elif mode == "scan":
            from_date, to_date = _resolve_dates(vars(args), data_dir)
            result = mode_scan(data_dir, from_date, to_date)

        elif mode == "sleep":
            from_date, to_date = _resolve_dates(vars(args), data_dir)
            result = mode_sleep(data_dir, from_date, to_date)

        elif mode == "activity":
            from_date, to_date = _resolve_dates(vars(args), data_dir)
            result = mode_activity(data_dir, from_date, to_date)

        elif mode == "heart":
            from_date, to_date = _resolve_dates(vars(args), data_dir)
            result = mode_heart(data_dir, from_date, to_date)

        else:
            result = {"error": f"Unknown mode: {mode}"}

        print(json.dumps(result, indent=2, default=str))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
