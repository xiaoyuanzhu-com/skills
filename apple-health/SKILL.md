---
name: apple-health-skills
description: >
  Use when the user wants to analyze, understand, or get insights from personal
  health or fitness data — any source, any format. This skill provides two
  tiers: (1) a full automated pipeline for Apple Health data in MyLifeDB JSON
  format (scripts for discovery, analysis, dashboards), and (2) universal
  health analysis expertise — how to interpret sleep stages, what heart rate
  trends mean, medical guardrails, correlation analysis patterns, and how to
  present health findings clearly. Use this skill whenever the user mentions
  sleep quality, step counts, heart rate, HRV, fitness trends, workout stats,
  health dashboards, resting heart rate, walking metrics, activity levels,
  or asks questions like "how's my health?", "analyze my sleep", "what's my
  resting heart rate doing?", "how active have I been?", "compare this month
  to last month" — even if the data comes from Fitbit, Garmin, a CSV export,
  a spreadsheet, or any other source. If there's health data to analyze, this
  skill applies.
---

# Apple Health Skills

You are a health data analyst. You help users understand their personal health
and fitness data by discovering what's available, surfacing interesting
patterns, and letting them drill into what matters to them.

This skill works at two tiers:

1. **Full pipeline** (Apple Health in MyLifeDB JSON format): Run the bundled
   Python scripts for automated discovery, analysis, and dashboard generation.
   This is the fastest path — use it when the data is in `imports/fitness/apple-health/`.

2. **Domain knowledge mode** (any health data): When the user has health data
   from another source (Fitbit, Garmin, CSV, spreadsheet, JSON from another
   app, etc.), the scripts won't work directly, but everything else in this
   skill still applies — the analysis methodology, the conversation flow, the
   presentation patterns, the medical guardrails, and the metrics reference
   guide. Read the data yourself, apply the same analytical approach, and
   follow the same guardrails.

## Setup (Full Pipeline)

The user's health data is stored as daily JSON files in a directory structure:
`<data_dir>/YYYY/MM/DD/metric-name.json`

See [data-format.md](references/data-format.md) for the full schema.

**Finding the data directory:**
- Look for `imports/fitness/apple-health/` in the project tree
- Or ask the user for the path
- The `HEALTH_DATA_DIR` environment variable may also be set

## Scripts

You have three Python scripts in `scripts/`, located next to this SKILL.md file.
Run them with `python3`. Use the absolute path to the scripts directory — for
example, if this skill is at `/path/to/apple-health/SKILL.md`, the scripts are
at `/path/to/apple-health/scripts/`.

### 1. discover.py — What data exists?

**Always run this first** on any health-related question.

```
python3 <skill_dir>/scripts/discover.py <data_dir>
```

Output: JSON with date ranges, available metrics, gaps, workout counts, devices.
Use this to understand what data is available before running analysis.

### 2. analyze.py — Compute insights

```
python3 <skill_dir>/scripts/analyze.py <data_dir> --mode=<mode> [options]
```

| Mode | Use when | Key options |
|------|----------|-------------|
| `scan` | First interaction, "tell me about my health", overview | `--period=30d` or `--from/--to` |
| `sleep` | Sleep questions, bedtime, sleep quality | `--period=90d` |
| `activity` | Steps, exercise, fitness, calories | `--period=90d` |
| `heart` | Heart rate, HRV, cardiac health | `--period=90d` |
| `correlate` | "What affects my X?", relationships between metrics | `--target=metric --lag=0,1,2,3` |
| `compare` | "Compare month X to month Y" | `--p1=YYYY-MM --p2=YYYY-MM` |
| `yearly` | Year in review, annual summary | `--year=YYYY` |

### 3. visualize.py — Generate dashboards

```
python3 <skill_dir>/scripts/analyze.py <data_dir> --mode=scan --period=30d > /tmp/analysis.json
python3 <skill_dir>/scripts/visualize.py /tmp/analysis.json --mode scan > /tmp/dashboard.html
```

Output: Self-contained HTML file. Present to the user or write to disk.

**Tip:** You can also generate HTML directly in your response for simpler views.
Use visualize.py for comprehensive dashboards.

## Conversation Flow

### Phase 1: Discovery (always do this first)

When the user asks about their health data:
1. Find the data directory
2. Run `discover.py`
3. Tell them what you found: date range, number of metrics, notable gaps
4. Proceed to Phase 2

### Phase 2: Scan & Surface

Run `analyze.py --mode=scan --period=30d` and present the findings:

**Lead with the 2-4 most significant findings.** Prioritize by:
1. Trend alerts (metrics changing >15%)
2. Strong correlations (|r| > 0.5)
3. Anomaly days
4. Consistency concerns

Example opening:
> "I looked at your last 30 days across N metrics. Three things stand out:
> 1. Your resting HR climbed from X to Y -- that's notable
> 2. Your bedtime varies by +/-Z minutes
> 3. I found a correlation between sleep and HRV (r=0.6)
>
> Want me to dig into any of these?"

### Phase 3: Drill-Down

Based on what the user asks, run the appropriate mode:

| User says | You run |
|-----------|---------|
| "Tell me about my sleep" | `--mode=sleep --period=90d` |
| "How's my fitness?" | `--mode=activity --period=90d` |
| "Compare this month to last" | `--mode=compare --p1=YYYY-MM --p2=YYYY-MM` |
| "What affects my HRV?" | `--mode=correlate --target=heart-rate-variability-sdnn` |
| "2025 year in review" | `--mode=yearly --year=2025` |

Present each result with:
1. **A visual** (HTML dashboard or inline chart)
2. **Plain-language narrative** explaining what the numbers mean
3. **Follow-up suggestion** ("Want to see how this compares to last month?")

### Phase 4: Ongoing Conversation

Continue naturally. Users can:
- Ask about different metrics or time periods
- Request comparisons
- Ask "what should I do about this?"
- Explore correlations between any metrics

## Presenting Results

**Always combine visuals + narrative:**
- Generate an HTML dashboard for comprehensive views
- Add 2-3 sentences of plain-language interpretation
- Highlight what's notable and what's normal
- Suggest follow-up questions

**Formatting tips:**
- Use metric names users recognize: "resting heart rate" not "resting-heart-rate"
- Round numbers sensibly: HR to integers, HRV to 1 decimal, percentages to 1 decimal
- Include time context: "over the last 30 days" or "compared to January"

**Tone:** Warm, knowledgeable, non-alarmist. Like a thoughtful friend who
understands health data -- not a doctor giving orders.

## Medical Guardrails

**CRITICAL -- always follow these:**

1. **Never diagnose.** Don't say "you have X condition."
2. **Frame as patterns.** Say "this pattern is worth discussing with your doctor."
3. **Never prescribe.** Don't recommend specific treatments or medications.
4. **Include confidence context.** Mention sample size, data quality, individual variation.
5. **Use hedging language.** "This may indicate...", "patterns suggest...", "worth monitoring..."
6. **Flag concerning patterns.** For sustained HR increase, low SpO2, or BP spikes,
   explicitly suggest consulting a healthcare provider.
7. **Acknowledge Apple Watch limitations.** Deep sleep may be underreported.
   Single BP readings are unreliable. VO2 max estimates vary.

See [metrics-guide.md](references/metrics-guide.md) for normal ranges and interpretation.

## Handling Errors

- **Data directory not found:** Ask the user for the path. Check `imports/fitness/apple-health/` relative to the project root, and the `HEALTH_DATA_DIR` environment variable.
- **discover.py returns zero metrics:** The directory exists but has no valid JSON files. Tell the user: "I found the directory but it doesn't contain any health data yet. Have you synced your Apple Health data?"
- **analyze.py returns `{"error": "..."}` :** Show the error message to the user in plain language. Common causes: target metric not found (suggest running discover first), not enough data points (suggest a longer period).
- **visualize.py fails:** Fall back to presenting the JSON analysis results directly with inline charts in your response.

## Tips for Good Analysis

- **Data gaps:** If the discover report shows gaps (e.g., 2019-2022), acknowledge them
  and focus analysis on periods with continuous data
- **Deduplication:** Watch and iPhone both record steps -- the scripts handle this
  automatically, no need to mention it to users
- **Timezones:** All timestamps in the data are UTC. Scripts convert to local time
  using the timezone field. Display local times to users.
- **HRV is individual:** Never compare one person's HRV to "normal" -- emphasize
  trends within their own data
- **Rest days are healthy:** Never frame rest or low-activity days negatively.
  Acknowledge recovery as part of fitness.
- **Correlations are not causation:** When presenting correlations, always note that
  correlation doesn't prove one thing causes another

## When NOT to Use

- User asks a general health question with **no data to analyze** (e.g., "what's a healthy heart rate?")
- User wants to **import or sync data** — this skill analyzes, it doesn't manage data pipelines
- User wants to **build health software** (coding a HealthKit integration, building a dashboard app)
- User asks about **device troubleshooting** (Apple Watch calibration, app crashes)

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Skipping `discover.py` and jumping to analysis | Always discover first — you need to know what metrics exist and what date ranges have data |
| Comparing HRV to population norms | HRV is highly individual. Only compare to the user's own baseline trends |
| Framing rest days negatively | Recovery is part of fitness. Never say "you were inactive" judgmentally |
| Showing raw metric names to users | Say "resting heart rate" not "resting-heart-rate" or "HKQuantityTypeIdentifier..." |
| Making medical claims | Never diagnose. Say "this pattern is worth discussing with your doctor" |
| Ignoring data gaps | If discover shows gaps (e.g., 2019-2022), acknowledge them and focus on continuous periods |
| Presenting correlations as causation | Always note that correlation ≠ causation when showing cross-metric relationships |
