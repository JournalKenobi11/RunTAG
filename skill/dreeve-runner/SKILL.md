---
name: dreeve-runner
description: >-
  Use this skill whenever the user asks questions about their running activities, workouts,
  pace, heart rate, mileage, training zones, or performance history from Dreeve / Runwise.
  Provides instant access to pre-aggregated data and charting tools with minimal token usage.
---

# Dreeve Runner Analytics Skill

This skill provides direct, token-optimized access to the user's Dreeve running database without writing ad-hoc code or searching filesystem paths.

**Database Path:** `/home/journalkenobi/projects/dreeve/storage/database/dreeve.db`  
**Execution Environment:** `/home/journalkenobi/miniconda3/envs/ml_env/bin/python`  
**Core Engine:** `/home/journalkenobi/tools/dreeve/dreeve_engine.py`

---

## 1. Quick Execution Guide (Minimal Tokens)

DO NOT write custom python scripts or search for sqlite files. Use the pre-built CLI engine or MCP tools:

### A. High-Level Summary & Training Zones (~150 tokens)
```bash
/home/journalkenobi/miniconda3/envs/ml_env/bin/python /home/journalkenobi/tools/dreeve/dreeve_engine.py summary --days 60
```
*Returns:* Total activities, mileage, active time, avg pace, best pace, HR min/max/mean, zone breakdown, and pace-HR correlation ($r$, $R^2$).

### B. List Specific Runs & Workouts (~200 tokens)
```bash
/home/journalkenobi/miniconda3/envs/ml_env/bin/python /home/journalkenobi/tools/dreeve/dreeve_engine.py activities --days 60 --limit 15 --with-hr
```
*Optional flags:*
* `--with-hr`: Only return workouts with recorded heart rate.
* `--search "HIIT"`: Search workouts by name or description.
* `--limit 10`: Limit rows to protect context size.

### C. Automated Chart Generation
```bash
/home/journalkenobi/miniconda3/envs/ml_env/bin/python /home/journalkenobi/tools/dreeve/dreeve_engine.py plot --type pace_vs_hr --days 60 --theme dark
```
*Supported chart types:*
* `--type pace_vs_hr`: Standalone Pace vs Heart Rate scatter with zone shading and regression line.
* `--type dashboard`: 2-panel figure showing scatter efficiency curve and 60-day longitudinal progression.
* `--theme dark` or `--theme light`.
* `--out /path/to/custom_name.png`: Specify custom output destination.

### D. Custom Read-Only Queries
For questions requiring custom filtering or calculations:
```bash
/home/journalkenobi/miniconda3/envs/ml_env/bin/python /home/journalkenobi/tools/dreeve/dreeve_engine.py query --sql "SELECT name, distance, movingTimeInSeconds FROM Activity WHERE distance > 5000 LIMIT 10"
```

---

## 2. Key Data Characteristics & Context
* **Heart Rate Data:** Continuous optical heart rate telemetry began on **October 2, 2026** (following NoiseFit watch integration). Runs before October 2, 2026 lack heart rate streams.
* **Pace Metric:** Average pace is calculated as active moving time over GPS distance ($T / D$ in min/km).
* **HR Zones:**
  * Zone 1: Active Recovery (< 130 bpm)
  * Zone 2: Aerobic Base (130 – 145 bpm)
  * Zone 3: Tempo / Aerobic Endurance (145 – 155 bpm)
  * Zone 4+: Threshold / High Intensity (> 155 bpm)
