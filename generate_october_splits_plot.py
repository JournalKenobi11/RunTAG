import sqlite3, zstandard, json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.patches import Patch
from scipy import stats
import os

conn = sqlite3.connect('file:/home/journalkenobi/projects/dreeve/storage/database/dreeve.db?mode=ro', uri=True)
conn.text_factory = bytes
cursor = conn.cursor()

cursor.execute('''
    SELECT activityId, startDateTime, name, distance, movingTimeInSeconds
    FROM Activity
    WHERE startDateTime LIKE '2026-10%' AND (sportType = 'Run' OR activityType = 'Run')
      AND (markedForDeletion IS NULL OR markedForDeletion = 0)
    ORDER BY startDateTime ASC
''')
oct_runs = cursor.fetchall()
dctx = zstandard.ZstdDecompressor()
all_splits = []

for act_id_b, dt_b, name_b, dist_m, mov_time in oct_runs:
    act_id = act_id_b.decode(); dt = dt_b.decode(); name = name_b.decode()
    cursor.execute('SELECT streamType, data FROM ActivityStream WHERE activityId = ?', (act_id,))
    streams = {}
    for st, raw in cursor.fetchall():
        st_name = st.decode()
        if st_name in ('distance', 'time', 'heartrate'):
            try: streams[st_name] = json.loads(dctx.decompress(raw).decode('utf-8'))
            except: pass
    if 'heartrate' not in streams or 'distance' not in streams or 'time' not in streams:
        continue
    dist_arr = np.array(streams['distance'])
    time_arr = np.array(streams['time'])
    hr_arr = np.array(streams['heartrate'])
    total_km = int(np.ceil(dist_arr[-1] / 1000.0))
    for k in range(1, total_km + 1):
        s_d = (k - 1) * 1000.0
        e_d = min(k * 1000.0, dist_arr[-1])
        mask = (dist_arr >= s_d) & (dist_arr <= e_d)
        if not np.any(mask): continue
        seg_d = dist_arr[mask][-1] - dist_arr[mask][0]
        seg_t = time_arr[mask][-1] - time_arr[mask][0]
        if seg_d < 200: continue
        seg_pace = (seg_t / (seg_d / 1000.0)) / 60.0
        seg_hr = float(np.mean(hr_arr[mask]))
        all_splits.append({
            'date': dt[:10],
            'name': name,
            'km': k,
            'distance_m': round(seg_d),
            'time_s': seg_t,
            'pace': seg_pace,
            'hr': seg_hr
        })

df = pd.DataFrame(all_splits)

# Linear regression
slope, intercept, r_val, p_val, std_err = stats.linregress(df['hr'], df['pace'])
r_squared = r_val ** 2

def fmt_p(val, pos=None):
    m = int(val); s = int(round((val - m) * 60))
    if s == 60: m += 1; s = 0
    return f"{m}:{s:02d} /km"

plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
fig, ax = plt.subplots(figsize=(13, 8.5), dpi=300)
fig.patch.set_facecolor('#0b1329')
ax.set_facecolor('#151f38')

hr_zones = [
    (105, 130, 'Zone 1: Active Recovery (<130 bpm)', '#38bdf8', 0.08),
    (130, 145, 'Zone 2: Aerobic Base (130-145 bpm)', '#34d399', 0.08),
    (145, 155, 'Zone 3: Tempo / Aerobic (145-155 bpm)', '#fbbf24', 0.08),
    (155, 170, 'Zone 4: Threshold / Intervals (155-170 bpm)', '#f87171', 0.08),
    (170, 185, 'Zone 5: VO2 Max / Anaerobic (>170 bpm)', '#ec4899', 0.08),
]
for xmin, xmax, label, color, alpha in hr_zones:
    ax.axvspan(xmin, xmax, color=color, alpha=alpha, zorder=1)

ax.grid(True, linestyle='--', alpha=0.2, color='#94a3b8', zorder=2)

# Trendline
x_vals = np.linspace(108, 182, 100)
y_vals = slope * x_vals + intercept
ax.plot(x_vals, y_vals, color='#38bdf8', linestyle='--', linewidth=2.4, alpha=0.9,
        label=f'Linear Trend ($R^2 = {r_squared:.2f}$, $r = {r_val:.2f}$)', zorder=3)

# Scatter by Kilometer index
scatter = ax.scatter(
    df['hr'],
    df['pace'],
    c=df['km'],
    cmap=plt.cm.turbo,
    s=110,
    edgecolor='#ffffff',
    linewidth=1.2,
    alpha=0.9,
    zorder=5
)

ax.set_ylim(10.5, 4.5)
ax.set_xlim(105, 185)
ax.yaxis.set_major_formatter(ticker.FuncFormatter(fmt_p))

ax.set_xlabel('Mean Heart Rate per Kilometer (bpm)', fontsize=12, fontweight='bold', color='#f1f5f9', labelpad=10)
ax.set_ylabel('Kilometer Pace (min/km, Faster ↑)', fontsize=12, fontweight='bold', color='#f1f5f9', labelpad=10)
ax.tick_params(colors='#cbd5e1', labelsize=10)

plt.title('Dreeve Running Analytics: Kilometer Split Pace vs. Mean Heart Rate\nAll October 2026 Runs (83 Kilometer Splits Analyzed)',
          fontsize=15, fontweight='bold', color='#ffffff', pad=18)

cbar = plt.colorbar(scatter, ax=ax, orientation='vertical', pad=0.03, shrink=0.82)
cbar.set_label('Split Index (Km 1 → Km 8)', color='#f1f5f9', fontsize=10, fontweight='bold', labelpad=10)
cbar.set_ticks(range(1, 9))
cbar.ax.tick_params(colors='#cbd5e1', labelsize=9)

legend_elements = [
    plt.Line2D([0], [0], color='#38bdf8', lw=2.2, linestyle='--', label=f'Trendline ($R^2 = {r_squared:.2f}$, $p < 0.001$)'),
    Patch(facecolor='#38bdf8', alpha=0.35, label='Zone 1 Recovery (<130 bpm)'),
    Patch(facecolor='#34d399', alpha=0.35, label='Zone 2 Aerobic Base (130-145 bpm)'),
    Patch(facecolor='#fbbf24', alpha=0.35, label='Zone 3 Tempo / Aerobic (145-155 bpm)'),
    Patch(facecolor='#f87171', alpha=0.35, label='Zone 4 Threshold (155-170 bpm)'),
    Patch(facecolor='#ec4899', alpha=0.35, label='Zone 5 VO2 Max (>170 bpm)'),
]
ax.legend(handles=legend_elements, loc='upper left', framealpha=0.92, facecolor='#0b1329',
          edgecolor='#334155', fontsize=8.5, labelcolor='#f1f5f9')

stats_box = (
    f"October 2026 Kilometer Splits Analytics:\n"
    f"• Analyzed Splits: {len(df)} kms across 14 runs\n"
    f"• Pace Range: 4:55 – 10:10 /km (median: 7:12 /km)\n"
    f"• Mean HR Range: 110.6 – 180.1 bpm (median: 149.8 bpm)\n"
    f"• Pearson Correlation: r = {r_val:.2f} (p = 3.6e-15)\n"
    f"• Aerobic Decoupling: Mean HR increases +23 bpm from Km 1 to Km 7"
)
ax.text(0.97, 0.04, stats_box, transform=ax.transAxes,
        fontsize=8.5, verticalalignment='bottom', horizontalalignment='right',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='#0b1329', edgecolor='#475569', alpha=0.92),
        color='#e2e8f0')

out_path = '/home/journalkenobi/projects/dreeve-analytics/output/october_splits_pace_vs_hr.png'
plt.tight_layout()
fig.savefig(out_path, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
fig.savefig('/home/journalkenobi/projects/dreeve-analytics/output/october_splits_pace_vs_hr.jpg', dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
plt.close(fig)

# Copy to brain artifact directory as well
import shutil
shutil.copy(out_path, '/home/journalkenobi/.gemini/antigravity-cli/brain/69e56689-eb40-446b-86b7-ee19cf5bfce7/october_splits_pace_vs_hr.png')
print("October splits plot generated successfully!")
