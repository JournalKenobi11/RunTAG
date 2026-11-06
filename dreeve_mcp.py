#!/usr/bin/env python3
"""
Dreeve MCP Server for Antigravity & LLM Clients.
Exposes token-optimized running performance tools via Model Context Protocol stdio transport.
"""

import sys
import os
import json

# Ensure engine is on path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from mcp.server.mcpserver import MCPServer
import dreeve_engine

server = MCPServer("dreeve-analytics")

@server.tool()
def dreeve_summary(days: int = 60, sport: str = "Run") -> str:
    """
    Get a high-signal, token-efficient statistical summary of activities in Dreeve.
    Includes total mileage, active duration, average pace, HR zones, and pace-HR correlation.
    """
    try:
        data = dreeve_engine.get_summary(days=days, sport=sport)
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@server.tool()
def dreeve_activities(days: int = 60, limit: int = 15, with_hr_only: bool = False, search: str = None) -> str:
    """
    List recent activities from Dreeve in a compact, token-efficient format.
    Fields returned: id, date, name, distance_km, time, pace, avg_hr, speed_kmh.
    """
    try:
        activities = dreeve_engine.get_activities_list(
            days=days, limit=limit, with_hr_only=with_hr_only, search=search
        )
        return json.dumps(activities, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@server.tool()
def dreeve_splits(activity_id: str = None, days: int = None, month: str = None, summary_only: bool = False) -> str:
    """
    Analyze kilometer splits and mean heart rate from high-frequency streams.
    Returns exact split duration, pace, mean HR, correlation, and cardiac drift progression.
    activity_id: Specific activity ID (optional).
    days: Filter by recent N days (optional).
    month: Filter by month 'YYYY-MM' (e.g. '2026-10') (optional).
    summary_only: If True, returns aggregated metrics and cardiac drift (~100 tokens).
    """
    try:
        data = dreeve_engine.get_splits_analysis(
            activity_id=activity_id, days=days, month=month, summary_only=summary_only
        )
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@server.tool()
def dreeve_intervals(activity_id: str = None, plan: str = None, generate_plot: bool = True) -> str:
    """
    Analyze structured or variable interval workouts from raw telemetry streams.
    Supports variable intervals (e.g. '0.8k easy, 2x1.5k @ 6:00, 1k @ 7:00' or ladders/fartleks),
    calculates work vs recovery metrics, target deltas, HR recovery drops, and generates a visualization plot.
    activity_id: Specific activity ID or leave None for latest run.
    plan: Optional natural language description of intended workout plan.
    generate_plot: If True, generates and saves a publication-ready telemetry plot in output/.
    """
    try:
        data = dreeve_engine.get_interval_analysis(
            activity_id=activity_id, plan=plan, generate_plot=generate_plot
        )
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@server.tool()
def dreeve_plot(chart_type: str = "pace_vs_hr", days: int = 60, output_path: str = None, theme: str = "dark") -> str:
    """
    Generate and save a publication-ready running performance plot as PNG/JPG.
    Saved by default inside the dedicated 'output/' folder.
    chart_type: 'pace_vs_hr' (efficiency scatter) or 'dashboard' (2-panel scatter + timeline).
    theme: 'dark' (default) or 'light'.
    """
    try:
        result = dreeve_engine.generate_plot(
            chart_type=chart_type, days=days, output_path=output_path, theme=theme
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@server.tool()
def dreeve_query(sql: str) -> str:
    """
    Execute a safe, read-only SQL query on the Dreeve SQLite database.
    Restricted to SELECT/PRAGMA with automatic 30-row token limits.
    """
    try:
        result = dreeve_engine.execute_readonly_query(sql)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})

if __name__ == "__main__":
    server.run(transport="stdio")
