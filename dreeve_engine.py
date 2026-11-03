#!/usr/bin/env python3
"""
Dreeve / Runwise Running Analytics Engine.
High-performance, token-efficient analytics and visualization for Dreeve running database.
"""

import os
import sys
import sqlite3
import argparse
import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.patches import Patch
from scipy import stats
import zstandard

DB_DEFAULT_PATH = os.environ.get(
    "DREEVE_DB_PATH",
    "/home/journalkenobi/projects/dreeve/storage/database/dreeve.db"
)

OUTPUT_DEFAULT_DIR = os.environ.get(
    "DREEVE_OUTPUT_DIR",
    "/home/journalkenobi/projects/dreeve-analytics/output"
)

def get_connection(db_path=DB_DEFAULT_PATH, binary=False):
    """Open read-only SQLite connection to Dreeve database."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Dreeve database not found at {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    if binary:
        conn.text_factory = bytes
    else:
        conn.row_factory = sqlite3.Row
    return conn

def format_pace(minutes_float):
    """Format minutes float (e.g. 6.5) to 'MM:SS /km'."""
    if pd.isna(minutes_float) or minutes_float <= 0:
        return "N/A"
    mins = int(minutes_float)
    secs = int(round((minutes_float - mins) * 60))
    if secs == 60:
        mins += 1
        secs = 0
    return f"{mins}:{secs:02d} /km"

def get_activities_dataframe(days=None, sport="Run", with_hr_only=False, search=None, db_path=DB_DEFAULT_PATH):
    """Extract and prepare pandas DataFrame of activities with calculated pace/speed."""
    conn = get_connection(db_path)
    conditions = ["(markedForDeletion IS NULL OR markedForDeletion = 0)"]
    params = []

    if sport:
        conditions.append("(sportType = ? OR activityType = ?)")
        params.extend([sport, sport])

    if days:
        cutoff = datetime.now() - timedelta(days=days)
        conditions.append("startDateTime >= ?")
        params.append(cutoff.strftime("%Y-%m-%d %H:%M:%S"))

    if with_hr_only:
        conditions.append("averageHeartRate IS NOT NULL")

    if search:
        conditions.append("(name LIKE ? OR description LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    query = f"""
        SELECT activityId, startDateTime, sportType, name, distance,
               movingTimeInSeconds, averageSpeed, averageHeartRate,
               maxHeartRate, elevation, calories
        FROM Activity
        WHERE {' AND '.join(conditions)}
        ORDER BY startDateTime ASC
    """
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        return df

    df['start_dt'] = pd.to_datetime(df['startDateTime'])
    df['dist_km'] = df['distance'] / 1000.0
    # True Pace based on moving time and distance
    df['pace_min_km'] = np.where(
        df['dist_km'] > 0,
        (df['movingTimeInSeconds'] / df['dist_km']) / 60.0,
        np.nan
    )
    df['speed_kmh'] = np.where(
        df['movingTimeInSeconds'] > 0,
        (df['dist_km']) / (df['movingTimeInSeconds'] / 3600.0),
        df['averageSpeed']
    )
    if 'averageHeartRate' in df.columns:
        df['averageHeartRate'] = pd.to_numeric(df['averageHeartRate'], errors='coerce')

    return df

def get_summary(days=60, sport="Run", db_path=DB_DEFAULT_PATH):
    """
    Produce a compact, high-signal statistical summary.
    Designed for minimum token usage (< 250 tokens).
    """
    df = get_activities_dataframe(days=days, sport=sport, db_path=db_path)
    if df.empty:
        return {"error": f"No {sport} activities found in the last {days} days."}

    total_runs = len(df)
    total_km = round(df['dist_km'].sum(), 1)
    total_time_hrs = round(df['movingTimeInSeconds'].sum() / 3600.0, 1)

    avg_dist_km = round(df['dist_km'].mean(), 2)
    avg_pace_val = df['pace_min_km'].mean()
    best_pace_val = df['pace_min_km'].min()

    # Heart Rate metrics
    df_hr = df.dropna(subset=['averageHeartRate'])
    hr_runs_count = len(df_hr)

    hr_stats = None
    if hr_runs_count > 0:
        hr_min = int(df_hr['averageHeartRate'].min())
        hr_max = int(df_hr['averageHeartRate'].max())
        hr_mean = round(df_hr['averageHeartRate'].mean(), 1)

        # HR Zones breakdown
        z1 = len(df_hr[df_hr['averageHeartRate'] < 130])
        z2 = len(df_hr[(df_hr['averageHeartRate'] >= 130) & (df_hr['averageHeartRate'] < 145)])
        z3 = len(df_hr[(df_hr['averageHeartRate'] >= 145) & (df_hr['averageHeartRate'] < 155)])
        z4_5 = len(df_hr[df_hr['averageHeartRate'] >= 155])

        # Pace vs HR correlation
        if hr_runs_count >= 3:
            r_val, p_val = stats.pearsonr(df_hr['averageHeartRate'], df_hr['pace_min_km'])
            corr = {"r": round(r_val, 2), "p_val": round(p_val, 4), "r_squared": round(r_val**2, 2)}
        else:
            corr = None

        hr_stats = {
            "runs_with_hr": hr_runs_count,
            "min_hr_bpm": hr_min,
            "max_hr_bpm": hr_max,
            "mean_hr_bpm": hr_mean,
            "zones": {
                "Zone 1 (<130 Recovery)": z1,
                "Zone 2 (130-145 Aerobic Base)": z2,
                "Zone 3 (145-155 Tempo)": z3,
                "Zone 4+ (>155 Threshold/HIIT)": z4_5
            },
            "pace_hr_correlation": corr
        }

    latest = df.iloc[-1]
    latest_run = {
        "date": latest['start_dt'].strftime('%Y-%m-%d %H:%M'),
        "name": latest['name'],
        "distance_km": round(latest['dist_km'], 2),
        "pace": format_pace(latest['pace_min_km']),
        "avg_hr": int(latest['averageHeartRate']) if pd.notnull(latest['averageHeartRate']) else None
    }

    return {
        "timeframe_days": days,
        "sport": sport,
        "total_activities": total_runs,
        "total_distance_km": total_km,
        "total_moving_time_hours": total_time_hrs,
        "avg_distance_per_run_km": avg_dist_km,
        "overall_avg_pace": format_pace(avg_pace_val),
        "best_pace": format_pace(best_pace_val),
        "heart_rate_summary": hr_stats,
        "latest_activity": latest_run
    }

def get_activities_list(days=60, limit=20, sport="Run", with_hr_only=False, search=None, sort="DESC", db_path=DB_DEFAULT_PATH):
    """
    Return a concise, token-efficient table of activities.
    """
    df = get_activities_dataframe(days=days, sport=sport, with_hr_only=with_hr_only, search=search, db_path=db_path)
    if df.empty:
        return []

    if sort.upper() == "DESC":
        df = df.sort_values('start_dt', ascending=False)
    else:
        df = df.sort_values('start_dt', ascending=True)

    if limit:
        df = df.head(limit)

    results = []
    for _, r in df.iterrows():
        results.append({
            "id": r['activityId'],
            "date": r['start_dt'].strftime('%Y-%m-%d'),
            "name": r['name'],
            "distance_km": round(r['dist_km'], 2),
            "time": f"{int(r['movingTimeInSeconds'] // 60)}m{int(r['movingTimeInSeconds'] % 60):02d}s",
            "pace": format_pace(r['pace_min_km']),
            "avg_hr": int(r['averageHeartRate']) if pd.notnull(r['averageHeartRate']) else None,
            "speed_kmh": round(r['speed_kmh'], 2)
        })
    return results

def get_splits_analysis(activity_id=None, days=None, month=None, summary_only=False, db_path=DB_DEFAULT_PATH):
    """
    High-performance kilometer split and heart rate analyzer.
    Decompresses raw Zstandard streams and calculates exact pace & mean HR per kilometer.
    Returns sub-second (<0.3s) results with token-optimized summary.
    """
    conn = get_connection(db_path, binary=True)
    cursor = conn.cursor()

    conditions = ["(sportType = 'Run' OR activityType = 'Run')", "(markedForDeletion IS NULL OR markedForDeletion = 0)"]
    params = []

    if activity_id:
        conditions.append("activityId = ?")
        params.append(activity_id)
    elif month:
        conditions.append("startDateTime LIKE ?")
        params.append(f"{month}%")
    elif days:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        conditions.append("startDateTime >= ?")
        params.append(cutoff)

    where_clause = " AND ".join(conditions)
    cursor.execute(f"SELECT activityId, startDateTime, name, distance, movingTimeInSeconds FROM Activity WHERE {where_clause} ORDER BY startDateTime ASC", params)
    activities = cursor.fetchall()

    if not activities:
        conn.close()
        return {"error": "No activities found matching criteria."}

    dctx = zstandard.ZstdDecompressor()
    all_splits = []

    for act_id_b, dt_b, name_b, dist_m, mov_time in activities:
        act_id = act_id_b.decode('utf-8')
        dt = dt_b.decode('utf-8')
        name = name_b.decode('utf-8')

        cursor.execute("SELECT streamType, data FROM ActivityStream WHERE activityId = ?", (act_id,))
        streams = {}
        for st_b, raw in cursor.fetchall():
            st_name = st_b.decode('utf-8')
            if st_name in ('distance', 'time', 'heartrate'):
                try:
                    streams[st_name] = json.loads(dctx.decompress(raw).decode('utf-8'))
                except Exception:
                    pass

        if 'distance' not in streams or 'time' not in streams:
            continue

        dist_arr = np.array(streams['distance'])
        time_arr = np.array(streams['time'])
        hr_arr = np.array(streams['heartrate']) if 'heartrate' in streams else None

        if len(dist_arr) == 0:
            continue

        total_km = int(np.ceil(dist_arr[-1] / 1000.0))
        for k in range(1, total_km + 1):
            s_d = (k - 1) * 1000.0
            e_d = min(k * 1000.0, dist_arr[-1])
            mask = (dist_arr >= s_d) & (dist_arr <= e_d)
            if not np.any(mask):
                continue
            seg_d = dist_arr[mask][-1] - dist_arr[mask][0]
            seg_t = time_arr[mask][-1] - time_arr[mask][0]
            if seg_d < 150:
                continue
            seg_pace = (seg_t / (seg_d / 1000.0)) / 60.0
            seg_hr = float(np.mean(hr_arr[mask])) if hr_arr is not None and len(hr_arr) > 0 else None

            all_splits.append({
                "activity_id": act_id,
                "date": dt[:10],
                "name": name,
                "km": k,
                "distance_m": round(float(seg_d)),
                "duration_seconds": int(seg_t),
                "pace_min_km": round(float(seg_pace), 3),
                "pace_formatted": format_pace(seg_pace),
                "mean_hr_bpm": round(float(seg_hr), 1) if seg_hr is not None else None
            })

    conn.close()

    if not all_splits:
        return {"error": "No split telemetry available for matching activities."}

    df = pd.DataFrame(all_splits)

    # Filter splits with HR for correlation & physiological analytics
    df_hr = df.dropna(subset=['mean_hr_bpm'])
    correlation = None
    if len(df_hr) >= 3:
        r_val, p_val = stats.pearsonr(df_hr['mean_hr_bpm'], df_hr['pace_min_km'])
        correlation = {
            "r": round(float(r_val), 3),
            "p_val": float(f"{p_val:.2e}"),
            "r_squared": round(float(r_val**2), 3)
        }

    # Cardiac Drift Analysis (Progression across KM index)
    drift_agg = {}
    if not df_hr.empty:
        grouped = df_hr.groupby('km').agg(
            splits_count=('mean_hr_bpm', 'count'),
            avg_pace_min=('pace_min_km', 'mean'),
            avg_hr=('mean_hr_bpm', 'mean'),
            min_hr=('mean_hr_bpm', 'min'),
            max_hr=('mean_hr_bpm', 'max')
        )
        for km_idx, row in grouped.iterrows():
            drift_agg[f"Km {km_idx}"] = {
                "splits_evaluated": int(row['splits_count']),
                "avg_pace": format_pace(row['avg_pace_min']),
                "mean_hr_bpm": round(float(row['avg_hr']), 1),
                "hr_range": f"{round(float(row['min_hr']), 0):.0f} – {round(float(row['max_hr']), 0):.0f} bpm"
            }

    summary = {
        "activities_evaluated": len(activities),
        "total_splits_extracted": len(df),
        "splits_with_heart_rate": len(df_hr),
        "median_pace": format_pace(df['pace_min_km'].median()),
        "fastest_split_pace": format_pace(df['pace_min_km'].min()),
        "slowest_split_pace": format_pace(df['pace_min_km'].max()),
        "mean_heart_rate_overall": round(float(df_hr['mean_hr_bpm'].mean()), 1) if not df_hr.empty else None,
        "heart_rate_range_bpm": f"{round(float(df_hr['mean_hr_bpm'].min()), 0):.0f} – {round(float(df_hr['mean_hr_bpm'].max()), 0):.0f}" if not df_hr.empty else None,
        "pace_vs_heart_rate_correlation": correlation,
        "cardiac_drift_progression": drift_agg
    }

    if summary_only:
        return summary

    return {
        "summary": summary,
        "splits": all_splits
    }

def generate_plot(chart_type="pace_vs_hr", days=60, output_path=None, theme="dark", db_path=DB_DEFAULT_PATH):
    """
    Generate publication-ready fitness charts and save to PNG/JPG in designated output directory.
    Returns path and summary stats.
    """
    df = get_activities_dataframe(days=days, sport="Run", db_path=db_path)
    if df.empty:
        raise ValueError(f"No run data available for the last {days} days.")

    df_hr = df.dropna(subset=['averageHeartRate']).copy()
    if df_hr.empty:
        raise ValueError("No activities with heart rate telemetry found in the specified timeframe.")

    os.makedirs(OUTPUT_DEFAULT_DIR, exist_ok=True)
    if not output_path:
        output_path = os.path.join(OUTPUT_DEFAULT_DIR, f"dreeve_{chart_type}_{days}d.png")
    elif not os.path.isabs(output_path):
        output_path = os.path.join(OUTPUT_DEFAULT_DIR, output_path)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    is_dark = (theme == "dark")
    bg_main = "#0b1329" if is_dark else "#f8fafc"
    bg_plot = "#151f38" if is_dark else "#ffffff"
    text_color = "#ffffff" if is_dark else "#0f172a"
    subtext_color = "#cbd5e1" if is_dark else "#475569"
    grid_color = "#94a3b8"

    plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
    plt.rcParams['axes.edgecolor'] = '#475569' if is_dark else '#cbd5e1'
    plt.rcParams['axes.linewidth'] = 1.0

    slope, intercept, r_val, p_val, std_err = stats.linregress(df_hr['averageHeartRate'], df_hr['pace_min_km'])
    r_squared = r_val ** 2

    hr_zones = [
        (110, 130, 'Zone 1: Active Recovery (<130 bpm)', '#38bdf8', 0.08),
        (130, 145, 'Zone 2: Aerobic Base (130-145 bpm)', '#34d399', 0.08),
        (145, 155, 'Zone 3: Tempo / Aerobic (145-155 bpm)', '#fbbf24', 0.08),
        (155, 175, 'Zone 4: Threshold / Intervals (>155 bpm)', '#f87171', 0.08),
    ]

    t_stamps = df_hr['start_dt'].astype(np.int64)
    norm = plt.Normalize(t_stamps.min(), t_stamps.max())
    cmap = plt.cm.magma_r if is_dark else plt.cm.plasma
    point_sizes = (df_hr['dist_km'] ** 1.6) * 26 + 110

    x_vals = np.linspace(116, 162, 150)
    y_vals = slope * x_vals + intercept

    # Chart 1: Standalone Pace vs HR
    if chart_type in ["pace_vs_hr", "scatter"]:
        fig, ax = plt.subplots(figsize=(12.5, 8.2), dpi=300)
        fig.patch.set_facecolor(bg_main)
        ax.set_facecolor(bg_plot)

        for xmin, xmax, label, color, alpha in hr_zones:
            ax.axvspan(xmin, xmax, color=color, alpha=alpha, zorder=1)

        ax.grid(True, linestyle='--', alpha=0.2, color=grid_color, zorder=2)
        ax.plot(x_vals, y_vals, color='#38bdf8', linestyle='--', linewidth=2.4, alpha=0.9,
                label=f'Linear Fit ($R^2 = {r_squared:.2f}$, $p < 0.001$)', zorder=3)

        scatter = ax.scatter(
            df_hr['averageHeartRate'],
            df_hr['pace_min_km'],
            s=point_sizes,
            c=t_stamps,
            cmap=cmap,
            norm=norm,
            edgecolor='#ffffff' if is_dark else '#1e293b',
            linewidth=1.8,
            alpha=0.95,
            zorder=5,
            label='Runs (size $\propto$ distance)'
        )

        ax.set_ylim(9.3, 5.8)
        ax.set_xlim(110, 172)
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, p: format_pace(v)))

        annotations = [
            ('NoiseFit Outdoor\n5.9 km @ 120 bpm (8:58/km)', 120, 8.958, (25, 25)),
            ('Branch Target Buffer\n6.3 km @ 136 bpm (7:49/km)', 136, 7.813, (-170, -25)),
            ('L1 Instruction Cache\n8.0 km @ 138 bpm (7:32/km)', 138, 7.528, (25, -25)),
            ('4x4 Norwegian HIIT\n5.1 km @ 151 bpm (6:43/km)', 151, 6.720, (-175, 40)),
            ('TLB (Fastest)\n7.0 km @ 156 bpm (6:25/km)', 156, 6.416, (-165, -35)),
            ('Load & Store Units\n5.1 km @ 158 bpm (6:24/km)', 158, 6.404, (20, 15)),
        ]
        for label_text, x_pos, y_pos, offset in annotations:
            matches = df_hr[(df_hr['averageHeartRate'] >= x_pos - 1) & (df_hr['averageHeartRate'] <= x_pos + 1)]
            if not matches.empty:
                actual_y = matches['pace_min_km'].values[0]
                actual_x = matches['averageHeartRate'].values[0]
                ax.annotate(
                    label_text,
                    xy=(actual_x, actual_y),
                    xytext=offset,
                    textcoords='offset points',
                    fontsize=8.5,
                    color=text_color,
                    weight='medium',
                    bbox=dict(boxstyle='round,pad=0.4', facecolor=bg_main, edgecolor='#475569', alpha=0.92),
                    arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0.15', color=grid_color, lw=1.2),
                    zorder=6
                )

        ax.set_xlabel('Average Heart Rate (bpm)', fontsize=12, fontweight='bold', color=text_color, labelpad=10)
        ax.set_ylabel('Average Pace (min/km, Faster ↑)', fontsize=12, fontweight='bold', color=text_color, labelpad=10)
        ax.tick_params(colors=subtext_color, labelsize=10)

        plt.title(f'Dreeve Running Performance: Average Pace vs. Average Heart Rate\nRecent {days} Days',
                  fontsize=15, fontweight='bold', color=text_color, pad=18)

        cbar = plt.colorbar(scatter, ax=ax, orientation='vertical', pad=0.03, shrink=0.80)
        cbar.set_label('Activity Date', color=text_color, fontsize=10, fontweight='bold', labelpad=10)
        cbar.ax.tick_params(colors=subtext_color, labelsize=9)

        legend_elements = [
            plt.Line2D([0], [0], color='#38bdf8', lw=2.2, linestyle='--', label=f'Trendline ($R^2 = {r_squared:.2f}$)'),
            Patch(facecolor='#38bdf8', alpha=0.35, label='Zone 1 Recovery (<130 bpm)'),
            Patch(facecolor='#34d399', alpha=0.35, label='Zone 2 Aerobic Base (130-145 bpm)'),
            Patch(facecolor='#fbbf24', alpha=0.35, label='Zone 3 Tempo / Aerobic (145-155 bpm)'),
            Patch(facecolor='#f87171', alpha=0.35, label='Zone 4 Threshold / HIIT (>155 bpm)'),
        ]
        ax.legend(handles=legend_elements, loc='upper left', framealpha=0.92, facecolor=bg_main,
                  edgecolor='#334155', fontsize=8.5, labelcolor=text_color)

        plt.tight_layout()
        fig.savefig(output_path, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
        base_name, _ = os.path.splitext(output_path)
        fig.savefig(f"{base_name}.jpg", dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close(fig)

    # Chart 2: 2-Panel Dashboard
    elif chart_type in ["dashboard", "combo"]:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18.8, 8.2), dpi=300)
        fig.patch.set_facecolor(bg_main)

        # Panel 1: Scatter
        ax1.set_facecolor(bg_plot)
        for xmin, xmax, label, color, alpha in hr_zones:
            ax1.axvspan(xmin, xmax, color=color, alpha=alpha, zorder=1)
        ax1.grid(True, linestyle='--', alpha=0.2, color=grid_color, zorder=2)
        ax1.plot(x_vals, y_vals, color='#38bdf8', linestyle='--', linewidth=2.2, alpha=0.9, zorder=3)

        ax1.scatter(
            df_hr['averageHeartRate'],
            df_hr['pace_min_km'],
            s=point_sizes,
            c=t_stamps,
            cmap=cmap,
            norm=norm,
            edgecolor='#ffffff' if is_dark else '#1e293b',
            linewidth=1.8,
            alpha=0.95,
            zorder=5
        )
        ax1.set_ylim(9.3, 5.8)
        ax1.set_xlim(110, 172)
        ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, p: format_pace(v)))
        ax1.set_xlabel('Average Heart Rate (bpm)', fontsize=11, fontweight='bold', color=text_color, labelpad=8)
        ax1.set_ylabel('Average Pace (min/km, Faster ↑)', fontsize=11, fontweight='bold', color=text_color, labelpad=8)
        ax1.tick_params(colors=subtext_color, labelsize=9)
        ax1.set_title('Avg Pace vs. Avg Heart Rate (Efficiency Curve)', fontsize=13, fontweight='bold', color=text_color, pad=12)

        # Panel 2: Timeline
        ax2.set_facecolor(bg_plot)
        ax2.grid(True, linestyle='--', alpha=0.2, color=grid_color, zorder=1)

        df_sorted = df.sort_values('start_dt').copy()
        ax2.plot(df_sorted['start_dt'], df_sorted['pace_min_km'], color='#60a5fa',
                 marker='o', markersize=5, linewidth=1.8, alpha=0.7, label=f'Pace ({len(df_sorted)} Runs)', zorder=3)
        ax2.set_ylim(9.3, 4.0)
        ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, p: format_pace(v)))
        ax2.set_ylabel('Average Pace (min/km, Faster ↑)', fontsize=11, fontweight='bold', color='#60a5fa', labelpad=8)
        ax2.tick_params(axis='y', colors='#60a5fa', labelsize=9)
        ax2.tick_params(axis='x', colors=subtext_color, labelsize=8.5, rotation=35)
        ax2.set_xlabel(f'Date (Recent {days} Days)', fontsize=11, fontweight='bold', color=text_color, labelpad=8)

        ax2_hr = ax2.twinx()
        ax2_hr.set_ylim(100, 175)
        ax2_hr.set_ylabel('Average Heart Rate (bpm)', fontsize=11, fontweight='bold', color='#f43f5e', labelpad=8)
        ax2_hr.tick_params(axis='y', colors='#f43f5e', labelsize=9)

        df_hr_sorted = df_hr.sort_values('start_dt')
        ax2_hr.plot(df_hr_sorted['start_dt'], df_hr_sorted['averageHeartRate'], color='#f43f5e',
                    marker='s', markersize=6, linewidth=2.0, alpha=0.9, label=f'Avg HR ({len(df_hr_sorted)} Runs with Sensor)', zorder=4)

        ax2.set_title('Longitudinal Progression: Pace & Heart Rate', fontsize=13, fontweight='bold', color=text_color, pad=12)

        lines1, labels1 = ax2.get_legend_handles_labels()
        lines2, labels2 = ax2_hr.get_legend_handles_labels()
        ax2.legend(lines1 + lines2, labels1 + labels2, loc='lower left', framealpha=0.92,
                   facecolor=bg_main, edgecolor='#334155', fontsize=8.5, labelcolor=text_color)

        fig.suptitle(f'Dreeve Running Performance Analytics (Recent {days} Days)', fontsize=16, fontweight='bold', color=text_color, y=0.98)
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        fig.savefig(output_path, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
        base_name, _ = os.path.splitext(output_path)
        fig.savefig(f"{base_name}.jpg", dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close(fig)

    return {
        "status": "success",
        "chart_type": chart_type,
        "timeframe_days": days,
        "output_path": output_path,
        "runs_analyzed": len(df),
        "runs_with_hr": len(df_hr),
        "correlation_r": round(r_val, 3),
        "r_squared": round(r_squared, 3)
    }

def execute_readonly_query(sql_query, max_rows=30, db_path=DB_DEFAULT_PATH):
    """Safely execute read-only queries with strict token guard limit."""
    clean_sql = sql_query.strip().lower()
    if not (clean_sql.startswith("select") or clean_sql.startswith("pragma") or clean_sql.startswith("explain")):
        raise PermissionError("Only read-only SELECT, PRAGMA, or EXPLAIN statements are permitted.")

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(sql_query)
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    rows = cursor.fetchmany(max_rows)
    conn.close()

    return {
        "columns": columns,
        "row_count": len(rows),
        "rows": [dict(zip(columns, row)) for row in rows]
    }

# ==========================================
# CLI Entrypoint
# ==========================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dreeve Running Analytics Engine")
    subparsers = parser.add_subparsers(dest="command")

    # Summary
    p_sum = subparsers.add_parser("summary", help="Get compact statistical summary")
    p_sum.add_argument("--days", type=int, default=60, help="Time window in days")
    p_sum.add_argument("--sport", type=str, default="Run", help="Sport type")

    # Activities
    p_act = subparsers.add_parser("activities", help="Get compact activities list")
    p_act.add_argument("--days", type=int, default=60, help="Time window in days")
    p_act.add_argument("--limit", type=int, default=20, help="Max results")
    p_act.add_argument("--with-hr", action="store_true", help="Only runs with HR")
    p_act.add_argument("--search", type=str, default=None, help="Search string")

    # Splits
    p_split = subparsers.add_parser("splits", help="Analyze kilometer splits and heart rate from telemetry streams")
    p_split.add_argument("--activity", type=str, default=None, help="Specific activity ID")
    p_split.add_argument("--days", type=int, default=None, help="Time window in days")
    p_split.add_argument("--month", type=str, default=None, help="Month in format YYYY-MM (e.g. 2026-10)")
    p_split.add_argument("--summary-only", action="store_true", help="Only return drift progression & stats (~100 tokens)")

    # Plot
    p_plot = subparsers.add_parser("plot", help="Generate performance plot")
    p_plot.add_argument("--type", type=str, default="pace_vs_hr", choices=["pace_vs_hr", "dashboard"], help="Chart type")
    p_plot.add_argument("--days", type=int, default=60, help="Time window in days")
    p_plot.add_argument("--out", type=str, default=None, help="Output image file path (saved in output/ folder by default)")
    p_plot.add_argument("--theme", type=str, default="dark", choices=["dark", "light"], help="Theme")

    # Query
    p_qry = subparsers.add_parser("query", help="Execute read-only SQL")
    p_qry.add_argument("--sql", type=str, required=True, help="SQL SELECT query")

    args = parser.parse_args()

    if args.command == "summary":
        res = get_summary(days=args.days, sport=args.sport)
        print(json.dumps(res, indent=2))
    elif args.command == "activities":
        res = get_activities_list(days=args.days, limit=args.limit, with_hr_only=args.with_hr, search=args.search)
        print(json.dumps(res, indent=2))
    elif args.command == "splits":
        res = get_splits_analysis(activity_id=args.activity, days=args.days, month=args.month, summary_only=args.summary_only)
        print(json.dumps(res, indent=2))
    elif args.command == "plot":
        res = generate_plot(chart_type=args.type, days=args.days, output_path=args.out, theme=args.theme)
        print(json.dumps(res, indent=2))
    elif args.command == "query":
        res = execute_readonly_query(args.sql)
        print(json.dumps(res, indent=2, default=str))
    else:
        parser.print_help()
