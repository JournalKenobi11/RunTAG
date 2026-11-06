---
name: dreeve-runner
description: >-
  Use this skill whenever the user asks questions about their running activities, workouts,
  splits, kilometer pacing, heart rate, mileage, training zones, or performance history from Dreeve / Runwise.
  Provides instant access to pre-aggregated data, split analytics, and charting tools with minimal token usage.
---

# Dreeve Runner Analytics Skill

This skill provides direct, token-optimized access to the user's Dreeve running database without writing ad-hoc code or searching filesystem paths.

**Database Path:** `/home/journalkenobi/projects/dreeve/storage/database/dreeve.db`  
**Execution Environment:** `/home/journalkenobi/miniconda3/envs/ml_env/bin/python`  
**Core Engine:** `/home/journalkenobi/projects/dreeve-analytics/dreeve_engine.py`  
**Generated Charts/Plots Directory:** `/home/journalkenobi/projects/dreeve-analytics/output/`  
**Workout Reports Directory:** `/home/journalkenobi/projects/dreeve-analytics/reports/`  

---

## 1. Quick Execution Guide (Minimal Tokens)

DO NOT write custom python scripts or search for sqlite files. All generated plots and exports are automatically placed inside `/home/journalkenobi/projects/dreeve-analytics/output/`.
Whenever generating workout debriefs, session analyses, or markdown reports, save them directly to `/home/journalkenobi/projects/dreeve-analytics/reports/` (e.g., `workout_analysis_YYYYMMDD.md`). Never isolate them only in session-specific brain artifact folders.

### A. High-Level Summary & Training Zones (~150 tokens)
```bash
/home/journalkenobi/projects/dreeve-analytics/dreeve-cli summary --days 60
```
*Returns:* Total activities, mileage, active time, avg pace, best pace, HR min/max/mean, zone breakdown, and pace-HR correlation ($r$, $R^2$).

### B. Kilometer Splits & Cardiac Drift Analytics (~150 tokens)
```bash
# Instant cardiac drift progression across all October splits (summary only)
/home/journalkenobi/projects/dreeve-analytics/dreeve-cli splits --month 2026-10 --summary-only

# Splits for a specific activity or timeframe
/home/journalkenobi/projects/dreeve-analytics/dreeve-cli splits --activity <activity_id>
/home/journalkenobi/projects/dreeve-analytics/dreeve-cli splits --days 30
```
*Returns:* Decompressed sub-second telemetry with exact split time, pace, mean HR, and kilometer progression.

### C. Structured & Variable Interval Workout Analytics (~250 tokens)
```bash
# Auto-detect intervals for the latest run or specific activity
/home/journalkenobi/projects/dreeve-analytics/dreeve-cli intervals
/home/journalkenobi/projects/dreeve-analytics/dreeve-cli intervals --activity <activity_id>

# With an intended workout plan (supports arbitrary variable intervals & ladders)
/home/journalkenobi/projects/dreeve-analytics/dreeve-cli intervals --plan "0.8k easy, 2x1.5k @ 6:00, 1k @ 7:00"
/home/journalkenobi/projects/dreeve-analytics/dreeve-cli intervals --plan "1k warmup + 4x1K @6:15 with 90s walk + 0.5k cooldown"
```
*Returns:* Exact segment breakdown (warmup, work intervals, walk/jog recoveries, cooldown), target pace vs actual pace delta, intra-interval micro-splits, heart rate recovery drop during rest, and an annotated publication-ready telemetry plot in `output/`.

### D. List Specific Runs & Workouts (~200 tokens)
```bash
/home/journalkenobi/projects/dreeve-analytics/dreeve-cli activities --days 60 --limit 15 --with-hr
```
*Optional flags:*
* `--with-hr`: Only return workouts with recorded heart rate.
* `--search "HIIT"`: Search workouts by name or description.
* `--limit 10`: Limit rows to protect context size.

### E. Automated Chart Generation
```bash
/home/journalkenobi/projects/dreeve-analytics/dreeve-cli plot --type pace_vs_hr --days 60 --theme dark
```
*Supported chart types:*
* `--type pace_vs_hr`: Standalone Pace vs Heart Rate scatter with zone shading and regression line.
* `--type dashboard`: 2-panel figure showing scatter efficiency curve and 60-day longitudinal progression.
* `--theme dark` or `--theme light`.
* All output images (PNG + JPEG) are automatically saved to `/home/journalkenobi/projects/dreeve-analytics/output/`.

### F. Custom Read-Only Queries
For questions requiring custom filtering or calculations:
```bash
/home/journalkenobi/projects/dreeve-analytics/dreeve-cli query --sql "SELECT name, distance, movingTimeInSeconds FROM Activity WHERE distance > 5000 LIMIT 10"
```

---

## 2. Key Data Characteristics & Context
* **Heart Rate Data:** Continuous optical heart rate telemetry began on **October 2, 2026** (following NoiseFit watch integration). Runs before October 2, 2026 lack heart rate streams.
* **Stream Compression:** Second-by-second telemetry (`time`, `distance`, `heartrate`) is stored as Zstandard-compressed binary BLOBs in `ActivityStream`. Use `splits` command to decompress.
* **Pace Metric:** Average pace is calculated as active moving time over GPS distance ($T / D$ in min/km).
* **HR Zones:**
  * Zone 1: Active Recovery (< 130 bpm)
  * Zone 2: Aerobic Base (130 – 145 bpm)
  * Zone 3: Tempo / Aerobic Endurance (145 – 155 bpm)
  * Zone 4+: Threshold / High Intensity (> 155 bpm)
