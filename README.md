# Dreeve Running Analytics & MCP Server 🏃‍♂️📊

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-2.0+-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A high-performance, token-efficient analytics engine and [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server built for self-hosted [Dreeve](https://github.com/robiningelbrecht/dreeve) / Runwise fitness databases.

Designed specifically to empower AI pair-programming assistants (such as Google Antigravity, Claude, and ChatGPT) with instant, direct access to running metrics without burning tokens on raw SQL dumps, blind directory searches, or ad-hoc scripting.

---

## Architecture Overview

```mermaid
flowchart TD
    User["User Query / Workout Question"] --> Agent["AI Assistant (Antigravity / Claude / Cursor)"]
    
    subgraph Interfaces["Token-Efficient Interfaces"]
        Agent -->|"Native Tool Call"| MCP["Dreeve MCP Server (dreeve_mcp.py)"]
        Agent -->|"Direct Bash Command"| CLI["dreeve-cli (dreeve_engine.py)"]
    end
    
    subgraph CoreEngine["Core Analytics Engine"]
        MCP --> Engine["dreeve_engine.py"]
        CLI --> Engine
        Engine --> SQLite[("dreeve.db (Read-Only WAL Mode)")]
        Engine --> Visualizer["Matplotlib Chart Engine"]
    end
    
    Visualizer --> OutputDir["output/ (PNG & JPEG Visualizations)"]
    Engine -->|"Compact JSON (~150 tokens)"| Agent
    Agent --> User
```

---

## Key Highlights

* **Token-Optimized Aggregation:** Queries return compact, pre-summarized JSON payloads (~150–250 tokens), preventing context window exhaustion.
* **Instant Visualizations:** Generates publication-ready dark/light theme charts (`Pace vs. HR Scatter`, `Longitudinal Progression Dashboard`) saved automatically into a dedicated [`output/`](./output) folder.
* **Dual Interface:** Use as a native MCP server or as a standalone command-line tool via `dreeve-cli`.
* **Zero Database Contention:** Connects via URI read-only mode (`?mode=ro`) with SQLite Write-Ahead Logging (WAL) support, guaranteeing zero locks on the running Dreeve instance.
* **Built-in Physiology Metrics:** Computes moving pace ($T/D$), heart rate training zones (Zone 1 Recovery through Zone 4+ Threshold), and Pearson aerobic efficiency correlation ($r$, $R^2$).

---

## Directory Structure

```text
dreeve-analytics/
├── dreeve_engine.py       # Core analytics, statistics, and plotting engine
├── dreeve_mcp.py          # Model Context Protocol stdio server
├── dreeve-cli             # System executable wrapper
├── requirements.txt       # Python dependencies
├── config/
│   └── mcp_config.example.json  # Sample MCP client configuration
├── skill/
│   └── dreeve-runner/
│       └── SKILL.md       # Global Antigravity Agent Skill definition
├── output/                # Dedicated folder for generated plots & exports
│   ├── dreeve_pace_vs_heart_rate.png
│   ├── dreeve_pace_vs_heart_rate.jpg
│   ├── dreeve_pace_hr_dashboard.png
│   └── dreeve_pace_hr_dashboard.jpg
└── README.md
```

---

## Sample Visualizations

All visual exports are automatically routed to the [`output/`](./output) directory:

### 1. Standalone Pace vs. Heart Rate Scatter & Zone Efficiency
Shows individual runs with point size proportional to distance, colored by activity recency, with Heart Rate zone bands (Zone 1 to Zone 4) and linear regression fit ($R^2 = 0.82$).

![Pace vs Heart Rate](./output/dreeve_pace_vs_heart_rate.png)

### 2. Longitudinal Dashboard (Scatter + 60-Day Timeline)
Combines the cardiac efficiency curve with a dual-axis timeline of pacing and heart rate progression.

![Performance Dashboard](./output/dreeve_pace_hr_dashboard.png)

---

## Installation & Setup

### 1. Prerequisites
* Python 3.10+ (Recommended in a dedicated environment, e.g., `conda activate ml_env`)
* Access to your local `dreeve.db` SQLite database file.

### 2. Install Dependencies
```bash
git clone https://github.com/JournalKenobi/dreeve-analytics.git
cd dreeve-analytics
pip install -r requirements.txt
```

### 3. Environment Variables (Optional)
The engine defaults to standard paths, but can be customized:
```bash
export DREEVE_DB_PATH="/path/to/storage/database/dreeve.db"
export DREEVE_OUTPUT_DIR="/path/to/dreeve-analytics/output"
```

---

## CLI Usage (`dreeve-cli`)

A convenience wrapper is provided at `./dreeve-cli` (or link it to your `~/.local/bin/dreeve-cli`):

### Get High-Level Statistical Summary
```bash
dreeve-cli summary --days 60
```
**Example Output (~150 tokens):**
```json
{
  "timeframe_days": 60,
  "sport": "Run",
  "total_activities": 30,
  "total_distance_km": 132.1,
  "total_moving_time_hours": 15.5,
  "avg_distance_per_run_km": 4.4,
  "overall_avg_pace": "6:55 /km",
  "best_pace": "4:20 /km",
  "heart_rate_summary": {
    "runs_with_hr": 14,
    "min_hr_bpm": 120,
    "max_hr_bpm": 158,
    "mean_hr_bpm": 148.5,
    "zones": {
      "Zone 1 (<130 Recovery)": 1,
      "Zone 2 (130-145 Aerobic Base)": 3,
      "Zone 3 (145-155 Tempo)": 4,
      "Zone 4+ (>155 Threshold/HIIT)": 6
    },
    "pace_hr_correlation": {
      "r": -0.9,
      "p_val": 0.0,
      "r_squared": 0.82
    }
  }
}
```

### List Activities
```bash
# Recent 10 runs with heart rate telemetry
dreeve-cli activities --days 30 --limit 10 --with-hr

# Search specific workouts
dreeve-cli activities --search "HIIT"
```

### Generate Performance Charts
```bash
# Standalone pace vs HR curve (saved to output/ folder)
dreeve-cli plot --type pace_vs_hr --days 60 --theme dark

# 2-Panel dashboard
dreeve-cli plot --type dashboard --days 60 --theme dark
```

### Safe Read-Only SQL Queries
```bash
dreeve-cli query --sql "SELECT name, distance, movingTimeInSeconds FROM Activity WHERE distance > 5000 LIMIT 5"
```

---

## MCP Server Integration

Add `dreeve` to your MCP configuration file (e.g. `~/.gemini/config/mcp_config.json` for Antigravity, or `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "dreeve": {
      "command": "/home/journalkenobi/miniconda3/envs/ml_env/bin/python",
      "args": [
        "/home/journalkenobi/projects/dreeve-analytics/dreeve_mcp.py"
      ],
      "env": {
        "PYTHONPATH": "/home/journalkenobi/projects/dreeve-analytics",
        "DREEVE_DB_PATH": "/home/journalkenobi/projects/dreeve/storage/database/dreeve.db",
        "DREEVE_OUTPUT_DIR": "/home/journalkenobi/projects/dreeve-analytics/output"
      }
    }
  }
}
```

### Exposed MCP Tools

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `dreeve_summary` | `days` (int, default 60), `sport` (str, default 'Run') | Returns high-level metrics, zone breakdowns, and pace-HR correlation in ~150 tokens. |
| `dreeve_activities` | `days` (int), `limit` (int), `with_hr_only` (bool), `search` (str) | Returns a concise tabular list of recent workouts. |
| `dreeve_plot` | `chart_type` ('pace_vs_hr' or 'dashboard'), `days` (int), `theme` ('dark' or 'light') | Renders and saves high-resolution charts to `output/`. |
| `dreeve_query` | `sql` (str) | Safely executes read-only SQL queries with automatic token safeguards. |

---

## License

This project is licensed under the [MIT License](LICENSE).
