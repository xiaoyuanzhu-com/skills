#!/usr/bin/env python3
"""Discover Apple Health data in MyLifeDB format.

Scans a data directory with structure YYYY/MM/DD/*.json and outputs
a JSON summary of available metrics, date range, gaps, workouts, and devices.

Usage: python3 discover.py <data_dir>
Output: JSON to stdout
"""

import json
import os
import sys
from datetime import date, timedelta

# How many samples to inspect per file for device detection (speed optimization)
MAX_SAMPLES_FOR_DEVICES = 5


def scan(data_dir):
    """Scan a MyLifeDB Apple Health data directory and return a summary dict.

    Args:
        data_dir: Path to the root data directory (contains YYYY/MM/DD/*.json).

    Returns:
        dict with keys: data_dir, date_range, total_days, gaps, metrics,
        workouts, devices.
    """
    data_dir = os.path.abspath(data_dir)

    all_dates = set()        # set of date objects for every day with data
    metrics = {}             # metric_name -> {"dates": set of date strings}
    workout_count = 0
    workout_types = set()
    devices = set()

    # Walk the YYYY/MM/DD directory structure
    for year_name in _listdir_sorted(data_dir):
        year_path = os.path.join(data_dir, year_name)
        if not os.path.isdir(year_path):
            continue
        # Must be a 4-digit year
        if not (len(year_name) == 4 and year_name.isdigit()):
            continue

        for month_name in _listdir_sorted(year_path):
            month_path = os.path.join(year_path, month_name)
            if not os.path.isdir(month_path):
                continue
            if not (len(month_name) == 2 and month_name.isdigit()):
                continue

            for day_name in _listdir_sorted(month_path):
                day_path = os.path.join(month_path, day_name)
                if not os.path.isdir(day_path):
                    continue
                if not (len(day_name) == 2 and day_name.isdigit()):
                    continue

                try:
                    day_date = date(int(year_name), int(month_name), int(day_name))
                except ValueError:
                    continue

                date_str = day_date.isoformat()
                day_has_data = False

                for filename in os.listdir(day_path):
                    if not filename.endswith(".json"):
                        continue

                    filepath = os.path.join(day_path, filename)
                    if not os.path.isfile(filepath):
                        continue

                    try:
                        with open(filepath, "r") as f:
                            data = json.load(f)
                    except (json.JSONDecodeError, OSError):
                        continue

                    if not isinstance(data, dict):
                        continue

                    # Workout file
                    if filename.startswith("workout-"):
                        workout_count += 1
                        activity = data.get("activity_type")
                        if activity:
                            workout_types.add(activity)
                        day_has_data = True
                        continue

                    # Metric file
                    metric_name = filename[:-5]  # strip .json
                    samples = data.get("samples")
                    if not isinstance(samples, list):
                        continue

                    day_has_data = True

                    if metric_name not in metrics:
                        metrics[metric_name] = {"dates": set()}
                    metrics[metric_name]["dates"].add(date_str)

                    # Extract devices from first few samples
                    for s in samples[:MAX_SAMPLES_FOR_DEVICES]:
                        device = s.get("device")
                        if device:
                            devices.add(device)

                if day_has_data:
                    all_dates.add(day_date)

    # Build output
    sorted_dates = sorted(all_dates)
    total_days = len(sorted_dates)

    if total_days > 0:
        date_range = {
            "earliest": sorted_dates[0].isoformat(),
            "latest": sorted_dates[-1].isoformat(),
        }
    else:
        date_range = {"earliest": None, "latest": None}

    # Compute gaps (3+ missing days)
    gaps = []
    if total_days >= 2:
        for i in range(len(sorted_dates) - 1):
            current = sorted_dates[i]
            next_day = sorted_dates[i + 1]
            missing = (next_day - current).days - 1
            if missing >= 3:
                gap_start = current + timedelta(days=1)
                gap_end = next_day - timedelta(days=1)
                gaps.append({
                    "from": gap_start.isoformat(),
                    "to": gap_end.isoformat(),
                    "days": missing,
                })

    # Build metrics summary
    metrics_summary = {}
    for name in sorted(metrics.keys()):
        date_set = metrics[name]["dates"]
        sorted_metric_dates = sorted(date_set)
        metrics_summary[name] = {
            "first": sorted_metric_dates[0],
            "last": sorted_metric_dates[-1],
            "days_with_data": len(date_set),
        }

    return {
        "data_dir": data_dir,
        "date_range": date_range,
        "total_days": total_days,
        "gaps": gaps,
        "metrics": metrics_summary,
        "workouts": {
            "count": workout_count,
            "types": sorted(workout_types),
        },
        "devices": sorted(devices),
    }


def _listdir_sorted(path):
    """List directory entries sorted, returning empty list if path doesn't exist."""
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 discover.py <data_dir>", file=sys.stderr)
        sys.exit(1)

    data_dir = sys.argv[1]
    if not os.path.isdir(data_dir):
        print(f"Error: {data_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    result = scan(data_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
