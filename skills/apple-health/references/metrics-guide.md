# Health Metrics Clinical Reference

Reference ranges and interpretation guidance for AI agents analyzing Apple Health data.

## Disclaimer

This guide provides general population reference ranges for contextualizing trends. **Never diagnose conditions or prescribe treatment.** Frame findings as "patterns worth discussing with your doctor." Individual baselines vary; trends over time matter more than isolated readings.

## Resting Heart Rate

- **Normal range:** 60-100 bpm. Well-trained athletes: 40-60 bpm.
- **Lower is generally better** for cardiovascular fitness.
- **Watch for:** sustained increase of +10 bpm over personal baseline (may indicate illness, stress, overtraining, or dehydration).
- **Context:** morning readings are most reliable; caffeine, stress, and illness elevate RHR.

## Heart Rate Variability (SDNN)

- **Typical range:** 20-100+ ms. Highly individual; younger and fitter people trend higher.
- **Higher is generally better** — indicates stronger parasympathetic tone.
- **Trends matter more than absolutes.** A personal drop of 20%+ sustained over days is more meaningful than comparing to population norms.
- **Context:** measured during sleep by Apple Watch. Alcohol, poor sleep, illness, and stress reduce HRV.

## Sleep

- **Total duration:** 7-9 hours recommended for adults.
- **Stage distribution (approximate):**
  - Core (N1+N2): 50-60%
  - Deep (N3): 13-23%
  - REM: 20-25%
- **Apple Watch caveat:** tends to underreport deep sleep compared to clinical polysomnography.
- **Bedtime consistency:** standard deviation under 30 minutes is ideal. Irregular schedules correlate with poorer sleep quality.
- **Watch for:** sustained total sleep under 6 hours, large drops in REM or deep percentage, highly irregular bedtimes.

## Steps

- **Guideline:** 7,000-10,000 steps/day for general health. Benefits plateau around 10,000-12,000.
- **Consistency matters more than big days.** A steady 8,000/day outweighs alternating 2,000 and 15,000.
- **Context:** step counts vary by occupation and lifestyle. Track personal trends rather than chasing a fixed target.

## Active Energy Burned

- **Highly individual** — depends on body weight, activity type, and fitness level.
- **No universal "good" number.** Track personal trends and weekly totals.
- **Watch for:** sudden sustained drops (reduced activity) or spikes (potential overtraining).

## Blood Pressure

| Category    | Systolic (mmHg) | Diastolic (mmHg) |
|-------------|-----------------|-------------------|
| Normal      | < 120           | < 80              |
| Elevated    | 120-129         | < 80              |
| Stage 1 HTN | 130-139        | 80-89             |
| Stage 2 HTN | >= 140         | >= 90             |

- **Single readings are unreliable.** Look at averages over days/weeks.
- **Context:** time of day, stress, caffeine, posture, and cuff fit all affect readings.

## Respiratory Rate

- **Normal range:** 12-20 breaths/min at rest.
- **Watch for:** sustained readings above 20 or significant upward trend from baseline.
- **Context:** measured during sleep by Apple Watch. Illness, anxiety, and pain can elevate it.

## Oxygen Saturation (SpO2)

- **Normal range:** 95-100%.
- **Below 95% sustained warrants medical attention.** Brief dips during sleep can be normal.
- **Context:** Apple Watch wrist-based SpO2 is less accurate than fingertip pulse oximeters. Use for trend detection, not precise values.

## Walking Metrics

| Metric                  | Typical Range     | Notes                              |
|-------------------------|-------------------|------------------------------------|
| Walking speed           | 1.2-1.4 m/s      | Declines with age; lower values correlate with frailty |
| Step length             | 0.6-0.8 m        | Shortened step length may indicate gait issues |
| Asymmetry               | < 4%              | Higher values suggest imbalance    |
| Double support time     | 20-40%            | Higher percentage = less stability |

- **Walking speed is a strong health indicator** in older adults; sustained decline warrants attention.
- **Asymmetry above 8-10%** may indicate injury or musculoskeletal issues.
