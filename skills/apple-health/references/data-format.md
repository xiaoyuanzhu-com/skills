# MyLifeDB Apple Health JSON Format

Reference for AI agents working with Apple Health data synced via the MyLifeDB app.

## Directory Layout

```
apple-health/
└── YYYY/MM/DD/
    ├── step-count.json
    ├── heart-rate.json
    ├── sleep-analysis.json
    ├── workout-<UUID>.json
    └── ...
```

One file per HealthKit type per day. File names are kebab-case with the `HKQuantityTypeIdentifier` / `HKCategoryTypeIdentifier` prefix stripped (e.g., `HKQuantityTypeIdentifierStepCount` -> `step-count.json`).

Days are determined by the sample's own timezone, **not UTC**.

## Top-Level File Structure

```json
{
  "date": "YYYY-MM-DD",
  "type": "HKQuantityTypeIdentifierStepCount",
  "timezone": "Asia/Shanghai",
  "unit": "count",
  "samples": [...]
}
```

| Field      | Type    | Description                                              |
|------------|---------|----------------------------------------------------------|
| `date`     | string  | Local date this file covers (`YYYY-MM-DD`)               |
| `type`     | string  | Full HealthKit type identifier                           |
| `timezone` | string  | IANA timezone used for day boundary                      |
| `unit`     | string? | Unit of measurement (quantity types only)                 |
| `samples`  | array   | All samples for this type+day, sorted by `(start, end, source)` |

## Quantity Samples

Used by step-count, heart-rate, active-energy-burned, etc.

```json
{"start": "2026-01-17T16:37:10.901Z", "end": "2026-01-17T16:46:20.452Z",
 "value": 200, "unit": "count", "type": "HKQuantityTypeIdentifierStepCount",
 "source": "com.apple.health.37928A11-...", "device": "Watch7,1"}
```

Fields: `start`, `end`, `value` (number), `unit`, `type`, `source`, `device`.

## Category Samples (Sleep)

```json
{"start": "2026-01-17T17:24:19.656Z", "end": "2026-01-17T17:27:49.348Z",
 "value": "asleepCore", "type": "HKCategoryTypeIdentifierSleepAnalysis",
 "source": "com.apple.health.37928A11-...", "device": "Watch7,1",
 "metadata": {"HKTimeZone": "Asia/Shanghai"}}
```

Fields: `start`, `end`, `value` (string enum: `asleepCore`, `asleepDeep`, `asleepREM`, `awake`), `type`, `source`, `device`, `metadata`.

## Workout Files

One file per workout event: `workout-<UUID>.json`. Placed in the day directory based on workout start date (device local time).

```json
{"uuid": "A1B2C3D4-...", "activity_type": "running",
 "start": "2026-01-18T01:30:00.000Z", "end": "2026-01-18T02:15:00.000Z",
 "duration_s": 2700, "source": "com.apple.health", "device": "Watch7,1",
 "synced_at": "2026-01-18T10:00:00.000Z",
 "device_info": {"name": "Apple Watch", "model": "Watch7,1", "systemVersion": "11.0"},
 "stats": {"distance": {"value": 5000, "unit": "m"}, "energy": {"value": 435, "unit": "kcal"}},
 "metadata": {...}, "route": [...]}
```

- **stats** — keys vary by activity type; each has `{value, unit}`.
- **route** — GPS track array, `null` for indoor workouts. Each point: `{t, lat, lon, alt, h_acc, v_acc, speed, speed_acc, course, course_acc}`. Coordinates are WGS 84; altitude, accuracy, and speed in metres/m/s; course in degrees from north.

## Timestamps

All `start` and `end` values are **UTC** (ISO 8601 with fractional seconds and `Z` suffix). Use the top-level `timezone` field to convert to local time for display or day-boundary logic.

## Sync Behavior

- Re-syncing **overwrites** files (each file is a complete snapshot, always a superset of prior versions).
- Files are **deterministic**: same data produces identical file content.

## Known Metric Types

**Quantity types:** step-count, heart-rate, active-energy-burned, basal-energy-burned, resting-heart-rate, oxygen-saturation, heart-rate-variability-sdnn, respiratory-rate, walking-speed, walking-step-length, distance-walking-running, flights-climbed, apple-exercise-time, apple-stand-time, apple-sleeping-wrist-temperature, blood-pressure-systolic, blood-pressure-diastolic, stair-ascent-speed, stair-descent-speed, walking-asymmetry-percentage, walking-double-support-percentage, walking-heart-rate-average.

**Category types:** sleep-analysis.

## Important Notes

- **Deduplication needed for steps**: both Watch and iPhone record steps. Prefer Watch as source of truth; filter by `device` field containing `Watch`.
- The exact set of available types depends on which the user has enabled and which have data.
