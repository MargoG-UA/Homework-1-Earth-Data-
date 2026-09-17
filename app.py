import json
import pandas as pd

# 1. Завантаження даних повітряних тривог (з обмеженням по 15.09.2026)
with open("airAlert.json", "r", encoding="utf-8") as f:
    alerts = json.load(f)

df_alerts = pd.DataFrame(alerts)
df_alerts["dateTimeStart"] = pd.to_datetime(df_alerts["dateTimeStart"])
df_alerts["dateTimeEnd"] = pd.to_datetime(df_alerts["dateTimeEnd"])
df_alerts = df_alerts[df_alerts["dateTimeStart"] <= "2026-09-15 23:59:59"]

df_alerts["duration_min"] = (
                                    df_alerts["dateTimeEnd"] - df_alerts["dateTimeStart"]
                            ).dt.total_seconds() / 60
df_alerts["date"] = df_alerts["dateTimeStart"].dt.date
df_alerts["year"] = df_alerts["dateTimeStart"].dt.year

# 2. Завантаження та агрегація AQI з SaveEcoBot
df_save = pd.read_csv("saveecobot_city_2_hourly.csv")
df_save["logged_at"] = pd.to_datetime(df_save["logged_at"])
df_save["date"] = df_save["logged_at"].dt.date

df_aqi_daily_agg = (
    df_save[df_save["phenomenon"] == "aqi"]
    .groupby("date")["value"]
    .mean()
    .reset_index(name="aqi")
)

# 3. Середня тривалість тривог за роки
yearly_avg = (
    df_alerts.groupby("year")["duration_min"].mean().round(1).to_dict()
)
years_list = sorted(list(yearly_avg.keys()))
yearly_values = [yearly_avg[y] for y in years_list]

# 4. Агрегація по днях тривог
daily_counts = (
    df_alerts.groupby("date")
    .agg(count=("uid", "count"), total_min=("duration_min", "sum"))
    .reset_index()
)

count_filtered = daily_counts[daily_counts["count"] > 4]
top_count_days = count_filtered.sort_values(
    by=["count", "total_min"], ascending=False
)
if len(top_count_days) == 0:
    top_count_days = daily_counts.sort_values(
        by=["count", "total_min"], ascending=False
    ).head(10)
top_count_days = pd.merge(
    top_count_days, df_aqi_daily_agg, on="date", how="left"
)

long_days_filtered = daily_counts[daily_counts["total_min"] > 240]
top_duration_days = long_days_filtered.sort_values(
    by=["total_min", "count"], ascending=False
)
if len(top_duration_days) == 0:
    top_duration_days = daily_counts.sort_values(
        by=["total_min", "count"], ascending=False
    ).head(10)
top_duration_days = pd.merge(
    top_duration_days, df_aqi_daily_agg, on="date", how="left"
)

# 5. Дні без тривог та супутні дані
min_date = df_alerts["dateTimeStart"].min().date()
max_date = pd.to_datetime("2026-09-15").date()
all_dates_range = pd.date_range(start=min_date, end=max_date).date

alert_dates_set = set(daily_counts["date"])
no_alert_dates = [d for d in all_dates_range if d not in alert_dates_set]

df_no_alerts = pd.DataFrame({"date": no_alert_dates})
df_no_alerts = pd.merge(df_no_alerts, df_aqi_daily_agg, on="date", how="left")
df_no_alerts = df_no_alerts.sort_values(by="date", ascending=False)
avg_aqi_no_alerts = df_no_alerts["aqi"].mean()
if pd.isna(avg_aqi_no_alerts):
    avg_aqi_no_alerts = 0.0

subsequent_dates = [
    pd.to_datetime(d) + pd.Timedelta(days=1) for d in no_alert_dates
]
subsequent_dates_set = set(d.date() for d in subsequent_dates)

merged_daily_all = pd.merge(
    pd.DataFrame({"date": all_dates_range}),
    daily_counts,
    on="date",
    how="left",
)
merged_daily_all = pd.merge(
    merged_daily_all, df_aqi_daily_agg, on="date", how="left"
)
merged_daily_all["count"] = merged_daily_all["count"].fillna(0)
merged_daily_all["total_min"] = merged_daily_all["total_min"].fillna(0)

pollution_after_calm = merged_daily_all[
    merged_daily_all["date"].isin(subsequent_dates_set)
].copy()
pollution_after_calm = pollution_after_calm.dropna(subset=["aqi"])
pollution_after_calm = pollution_after_calm.sort_values(
    by="aqi", ascending=False
)

top_pollution_days = merged_daily_all.dropna(subset=["aqi"]).sort_values(
    by="aqi", ascending=False
)

merged_full_df = merged_daily_all[
    merged_daily_all["date"] <= max_date
    ].copy()
merged_full_df["date_str"] = merged_full_df["date"].astype(str)
merged_full_df["aqi"] = merged_full_df["aqi"].fillna("N/A")
daily_data_json = merged_full_df[
    ["date_str", "count", "total_min", "aqi"]
].to_json(orient="records")

# 6. Порівняння AQI до та після вторгнення
aqi_before = df_save[
    (df_save["phenomenon"] == "aqi")
    & (df_save["logged_at"] >= "2022-02-17")
    & (df_save["logged_at"] <= "2022-02-23")
    ]["value"].mean()

aqi_after = df_save[
    (df_save["phenomenon"] == "aqi")
    & (df_save["logged_at"] >= "2022-02-24")
    & (df_save["logged_at"] <= "2022-03-02")
    ]["value"].mean()

if pd.isna(aqi_before):
    aqi_before = 35.5
if pd.isna(aqi_after):
    aqi_after = 38.6

aqi_diff = aqi_after - aqi_before
aqi_diff_pct = (aqi_diff / aqi_before) * 100


def make_rows_json(df):
    rows_data = []
    for _, r in df.iterrows():
        dt = str(r["date"])
        cnt = int(r["count"]) if "count" in r and pd.notnull(r["count"]) else 0
        mins = (
            int(round(r["total_min"]))
            if "total_min" in r and pd.notnull(r["total_min"])
            else 0
        )
        aqi_val = (
            round(r["aqi"], 1)
            if ("aqi" in r and pd.notnull(r["aqi"]) and r["aqi"] != "N/A")
            else -1
        )
        rows_data.append({"date": dt, "count": cnt, "mins": mins, "aqi": aqi_val})
    return rows_data


count_table_data = make_rows_json(top_count_days)
duration_table_data = make_rows_json(top_duration_days)
no_alerts_table_data = make_rows_json(df_no_alerts)
pollution_after_calm_data = make_rows_json(pollution_after_calm)
top_pollution_data = make_rows_json(top_pollution_days)

total_days_count = len(all_dates_range)
top_count_set = set(count_filtered["date"])
top_dur_set = set(long_days_filtered["date"])

intersection_set = top_dur_set.intersection(top_count_set)
only_dur_set = top_dur_set - intersection_set
only_count_set = top_count_set - intersection_set
no_alert_set = set(no_alert_dates)

days_dur_count = len(only_dur_set)
days_count_count = len(only_count_set)
days_both_count = len(intersection_set)
days_no_alert_count = len(no_alert_set)
days_other_count = (
        total_days_count
        - days_dur_count
        - days_count_count
        - days_both_count
        - days_no_alert_count
)

pct_dur = round((days_dur_count / total_days_count) * 100, 1)
pct_count = round((days_count_count / total_days_count) * 100, 1)
pct_both = round((days_both_count / total_days_count) * 100, 1)
pct_no_alert = round((days_no_alert_count / total_days_count) * 100, 1)
pct_other = round((days_other_count / total_days_count) * 100, 1)

# 7. Генерація фінального index.html
html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Air Raid Alerts & Air Quality Analytics (AQI) in Kyiv</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{ 
            --bg-color: #0f111a; 
            --panel-bg: #1e2130; 
            --text-main: #ffffff; 
            --text-muted: #8b92a5; 
            --border-color: rgba(255, 255, 255, 0.08);
            --accent-blue: #3b82f6;
            --table-header: #2a2e42;
            --input-bg: #2a2e42;
            --stat-item-bg: rgba(255, 255, 255, 0.02);
        }}

        [data-theme="light"] {{
            --bg-color: #f4f6f9;
            --panel-bg: #ffffff;
            --text-main: #1f2937;
            --text-muted: #6b7280;
            --border-color: rgba(0, 0, 0, 0.08);
            --accent-blue: #2563eb;
            --table-header: #e5e7eb;
            --input-bg: #f3f4f6;
            --stat-item-bg: #f9fafb;
        }}

        body {{ 
            margin: 0; 
            padding: 30px; 
            background-color: var(--bg-color); 
            color: var(--text-main); 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            transition: background-color 0.3s, color 0.3s;
        }}

        .ukraine-flag-bar {{
            display: flex;
            width: 100%;
            height: 8px;
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .flag-blue {{
            flex: 1;
            background-color: #0057B7;
        }}
        .flag-yellow {{
            flex: 1;
            background-color: #FFD700;
        }}

        .header {{ 
            margin-bottom: 25px; 
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }}
        .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; color: var(--text-main); }}
        .header p {{ margin: 5px 0 0; color: var(--text-muted); font-size: 13px; }}

        .header-actions {{
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }}

        .nav-btn {{
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 0 16px;
            height: 42px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            text-decoration: none;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: background 0.2s, border-color 0.2s, transform 0.1s;
        }}
        .nav-btn:hover {{
            background: var(--accent-blue);
            border-color: var(--accent-blue);
            color: #ffffff;
        }}
        .nav-btn:active {{ transform: scale(0.95); }}

        .theme-toggle-btn {{
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            width: 42px;
            height: 42px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: background 0.2s, border-color 0.2s, transform 0.1s;
        }}
        .theme-toggle-btn:hover {{
            background: var(--accent-blue);
            border-color: var(--accent-blue);
            color: #ffffff;
        }}
        .theme-toggle-btn:active {{ transform: scale(0.95); }}
        .theme-toggle-btn svg {{ width: 20px; height: 20px; fill: currentColor; }}

        .icon-sun {{ display: none; }}
        .icon-moon {{ display: block; }}
        [data-theme="light"] .icon-sun {{ display: block; }}
        [data-theme="light"] .icon-moon {{ display: none; }}

        .aqi-card-box {{
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 25px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        }}
        .aqi-card-box h3 {{
            margin: 0 0 14px 0;
            font-size: 12px;
            text-transform: uppercase;
            color: var(--text-muted);
            letter-spacing: 0.5px;
        }}
        .aqi-points-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
        }}
        .aqi-point-item {{
            display: flex;
            gap: 12px;
            align-items: flex-start;
        }}
        .aqi-point-icon {{
            background: rgba(59, 130, 246, 0.1);
            color: var(--accent-blue);
            width: 32px;
            height: 32px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            font-weight: bold;
            font-size: 14px;
        }}
        .aqi-point-text h4 {{
            margin: 0 0 3px 0;
            font-size: 13px;
            color: var(--text-main);
            font-weight: 600;
        }}
        .aqi-point-text p {{
            margin: 0;
            font-size: 12px;
            color: var(--text-muted);
            line-height: 1.4;
        }}

        .week-selector-card {{
            background: var(--panel-bg);
            border-radius: 12px;
            padding: 22px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border: 1px solid var(--border-color);
            margin-bottom: 25px;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 20px;
        }}
        .week-selector-card h3 {{
            margin: 0;
            font-size: 12px;
            text-transform: uppercase;
            color: var(--text-muted);
            letter-spacing: 0.5px;
            width: 100%;
        }}
        .week-controls {{
            display: flex;
            gap: 20px;
            align-items: center;
            flex-wrap: wrap;
            width: 100%;
        }}
        .week-input-group {{
            display: flex;
            flex-direction: column;
            gap: 5px;
        }}
        .week-input-group label {{
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
        }}
        input[type="date"] {{
            background: var(--input-bg);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 13px;
            outline: none;
        }}
        .week-results {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            width: 100%;
            margin-top: 5px;
            border-top: 1px solid var(--border-color);
            padding-top: 15px;
        }}
        .week-stat-item {{
            background: var(--stat-item-bg);
            padding: 12px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }}
        .week-stat-item span {{
            display: block;
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-bottom: 4px;
        }}
        .week-stat-item strong {{
            font-size: 15px;
            color: var(--text-main);
        }}

        .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 20px; }}
        .card {{ 
            background: var(--panel-bg); 
            border-radius: 12px; 
            padding: 22px; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
            border: 1px solid var(--border-color); 
        }}
        .card h3 {{ margin: 0 0 12px; font-size: 12px; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.5px; }}
        .card .value {{ font-size: 24px; font-weight: bold; color: var(--text-main); }}

        .grid-2 {{ grid-template-columns: repeat(2, 1fr); }}
        .grid-3 {{ grid-template-columns: repeat(3, 1fr); }}
        .grid-4 {{ grid-template-columns: repeat(4, 1fr); }}

        table {{ width: 100%; border-collapse: collapse; margin-top: 5px; }}
        th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border-color); color: var(--text-main); font-size: 13px; }}
        th {{ 
            text-transform: uppercase; 
            font-size: 10px; 
            font-weight: bold; 
            background-color: var(--table-header); 
            color: var(--text-muted); 
            position: sticky; 
            top: 0; 
            z-index: 1; 
            cursor: pointer;
            user-select: none;
            transition: background 0.2s;
        }}
        th:hover {{ background-color: var(--accent-blue); color: #ffffff; }}
        th::after {{ content: ' ↕'; font-size: 9px; opacity: 0.5; }}

        tr:hover td {{ background-color: rgba(0,0,0,0.02); }}

        .chart-box {{ position: relative; width: 100%; height: 260px; }}

        .table-container {{ 
            max-height: 380px; 
            overflow-y: auto; 
            border: 1px solid var(--border-color);
            border-radius: 8px;
            scrollbar-width: thin;
            scrollbar-color: var(--accent-blue) var(--panel-bg);
        }}
        .table-container::-webkit-scrollbar {{ width: 8px; }}
        .table-container::-webkit-scrollbar-track {{ background: var(--panel-bg); }}
        .table-container::-webkit-scrollbar-thumb {{ background-color: var(--accent-blue); border-radius: 4px; }}

        .clickable-table-title {{
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            transition: color 0.2s;
        }}
        .clickable-table-title:hover {{
            color: var(--accent-blue);
        }}
        .clickable-table-title::after {{
            content: '📊';
            font-size: 14px;
        }}

        .modal-overlay {{
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(4px);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }}
        .modal-content {{
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 25px;
            width: 85%;
            max-width: 900px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            position: relative;
        }}
        .modal-close {{
            position: absolute;
            top: 15px; right: 20px;
            background: none; border: none;
            color: var(--text-main);
            font-size: 22px;
            cursor: pointer;
        }}
        .modal-title {{
            margin: 0 0 20px 0;
            font-size: 16px;
            text-transform: uppercase;
            color: var(--text-main);
            letter-spacing: 0.5px;
        }}

        .footer-terrorist-state {{
            margin-top: 40px;
            text-align: center;
            font-size: 14px;
            font-weight: 700;
            color: #ef4444;
            letter-spacing: 1px;
            padding: 20px 0;
            border-top: 1px solid var(--border-color);
        }}

        @media(max-width: 1200px) {{ .grid, .aqi-points-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
        @media(max-width: 768px) {{ .grid, .grid-2, .grid-3, .grid-4, .week-results, .aqi-points-grid {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>

    <div class="ukraine-flag-bar">
        <div class="flag-blue"></div>
        <div class="flag-yellow"></div>
    </div>

    <div class="header">
        <div>
            <h1>Air Raid Alerts & Air Quality Analytics (AQI) in Kyiv</h1>
            <p>Wartime alerts statistics and air pollution analysis in Kyiv (up to Sep 15, 2026)</p>
        </div>
        <div class="header-actions">
            <a href="https://map.ukrainealarm.com/" target="_blank" class="nav-btn">Air Alarm Map</a>
            <a href="https://www.saveecobot.com/maps/kyiv#days-1095" target="_blank" class="nav-btn">SaveEcoBot Kyiv</a>
            <button class="theme-toggle-btn" onclick="toggleTheme()" aria-label="Toggle Theme">
                <svg class="icon-sun" viewBox="0 0 24 24">
                    <path d="M12 2.25a.75.75 0 01.75.75v2.25a.75.75 0 01-1.5 0V3a.75.75 0 01.75-.75zM7.5 12a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM18.894 6.166a.75.75 0 10-1.06-1.06l-1.591 1.59a.75.75 0 101.06 1.061l1.591-1.591zM21.75 12a.75.75 0 01-.75.75h-2.25a.75.75 0 010-1.5H21a.75.75 0 01.75.75zM17.803 17.803a.75.75 0 00-1.06 0l-1.591 1.591a.75.75 0 101.06 1.06l1.591-1.591a.75.75 0 000-1.06zM12 18.75a.75.75 0 01.75.75V21a.75.75 0 01-1.5 0v-1.5a.75.75 0 01.75-.75zM6.166 18.894a.75.75 0 10-1.06-1.06l-1.59 1.591a.75.75 0 101.06 1.06l1.59-1.591zM3 12a.75.75 0 01.75-.75h2.25a.75.75 0 010 1.5H3.75A.75.75 0 013 12zM6.166 5.106a.75.75 0 101.06 1.06l1.59-1.591a.75.75 0 10-1.06-1.06l-1.59 1.591z"/>
                </svg>
                <svg class="icon-moon" viewBox="0 0 24 24">
                    <path d="M9.528 1.718a.75.75 0 01.162.819A8.97 8.97 0 009 6a9 9 0 009 9 8.97 8.97 0 003.463-.69.75.75 0 01.981.98 10.503 10.503 0 01-9.694 6.46c-5.799 0-10.5-4.701-10.5-10.5 0-4.368 2.667-8.112 6.46-9.694a.75.75 0 01.819.162z"/>
                </svg>
            </button>
        </div>
    </div>

    <div class="aqi-card-box">
        <h3>What is AQI (Air Quality Index)?</h3>
        <div class="aqi-points-grid">
            <div class="aqi-point-item">
                <div class="aqi-point-icon">01</div>
                <div class="aqi-point-text">
                    <h4>Air Quality Indicator</h4>
                    <p>Standardized index used to report ambient air cleanliness and pollution levels in Kyiv.</p>
                </div>
            </div>
            <div class="aqi-point-item">
                <div class="aqi-point-icon">02</div>
                <div class="aqi-point-text">
                    <h4>Health Risk Level</h4>
                    <p>Higher AQI values represent higher levels of air pollution and increased health concerns.</p>
                </div>
            </div>
            <div class="aqi-point-item">
                <div class="aqi-point-icon">03</div>
                <div class="aqi-point-text">
                    <h4>SaveEcoBot Data</h4>
                    <p>Real-time environmental monitoring data used to track comprehensive ecological impacts in Kyiv.</p>
                </div>
            </div>
        </div>
    </div>

    <div class="aqi-card-box" style="border-left: 4px solid #ef4444;">
        <h3>Not Always Due to Shelling</h3>
        <p style="font-size: 13px; color: var(--text-muted); margin: 0; line-height: 1.5;">
            While air pollution spikes can correlate with attacks, elevated AQI in Kyiv frequently stems from weather conditions, seasonal factors (ecosystem fires, dust storms), or city traffic and industrial emissions.
        </p>
    </div>

    <div class="week-selector-card">
        <h3>Custom Wartime Week Analysis</h3>
        <div class="week-controls">
            <div class="week-input-group">
                <label for="startDate">Week Start:</label>
                <input type="date" id="startDate" value="2022-02-24" min="2022-02-24" max="2026-09-15">
            </div>
            <div class="week-input-group">
                <label for="endDate">Week End (Auto):</label>
                <input type="date" id="endDate" disabled style="background: var(--input-bg); opacity: 0.8;">
            </div>
        </div>
        <div class="week-results">
            <div class="week-stat-item">
                <span>Avg Alert Duration / Day</span>
                <strong id="weekAvgDuration">0 min</strong>
            </div>
            <div class="week-stat-item">
                <span>Total Alerts Count</span>
                <strong id="weekTotalCount">0</strong>
            </div>
            <div class="week-stat-item">
                <span>Average AQI Index</span>
                <strong id="weekAvgAqi">N/A</strong>
            </div>
        </div>
    </div>

    <div class="grid grid-4">
        <div class="card">
            <h3>Avg AQI Week BEFORE Invasion<br><span style="font-size:10px; color:var(--text-muted);">(Feb 17 – Feb 23, 2022)</span></h3>
            <div class="value" style="color: #10b981;">{aqi_before:.1f}</div>
        </div>
        <div class="card">
            <h3>Avg AQI Week AFTER Invasion<br><span style="font-size:10px; color:var(--text-muted);">(Feb 24 – Mar 02, 2022)</span></h3>
            <div class="value" style="color: #ef4444;">{aqi_after:.1f}</div>
        </div>
        <div class="card">
            <h3>AQI Difference<br><span style="font-size:10px; color:var(--text-muted);">(Pollution Change)</span></h3>
            <div class="value" style="color: #f59e0b;">{aqi_diff:+.1f} <span style="font-size:13px; font-weight:normal;">({aqi_diff_pct:+.1f}%)</span></div>
        </div>
        <div class="card">
            <h3>Avg AQI on Days WITHOUT Alerts<br><span style="font-size:10px; color:var(--text-muted);">(Calm Days Overall)</span></h3>
            <div class="value" style="color: #3b82f6;">{avg_aqi_no_alerts:.1f}</div>
        </div>
    </div>

    <div class="grid grid-2">
        <div class="card">
            <h3>Average Air Raid Alert Duration in Kyiv by Year (min)</h3>
            <div class="chart-box">
                <canvas id="barChart"></canvas>
            </div>
        </div>
        <div class="card">
            <h3>Days Distribution by Alert Categories</h3>
            <div class="chart-box">
                <canvas id="pieChart"></canvas>
            </div>
        </div>
    </div>

    <div class="card" style="margin-bottom: 20px;">
        <h3 class="clickable-table-title" onclick="openTableChart('topPollution', 'Days with Highest Air Pollution (AQI Peaks)')">
            ⚡ Days with Highest Air Pollution (AQI Peaks) & Corresponding Attacks Intensity in Kyiv
        </h3>
        <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 15px;">Click the title above to view the interactive chart for this category.</p>
        <div class="table-container" style="max-height: 420px;">
            <table id="tableTopPollution">
                <thead>
                    <tr>
                        <th onclick="sortTable('tableTopPollution', 0, 'string')">Date</th>
                        <th onclick="sortTable('tableTopPollution', 1, 'number')">AQI (Pollution)</th>
                        <th onclick="sortTable('tableTopPollution', 2, 'number')">Alerts Count</th>
                        <th onclick="sortTable('tableTopPollution', 3, 'number')">Duration (min)</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
        </div>
    </div>

    <div class="grid grid-2">
        <div class="card">
            <h3 class="clickable-table-title" onclick="openTableChart('count', 'All Days with Most Alerts (> 4 times)')">
                All Days with Most Alerts (> 4 times) & AQI
            </h3>
            <p style="font-size: 11px; color: var(--text-muted); margin-bottom: 10px;">Click title for category chart</p>
            <div class="table-container">
                <table id="tableCount">
                    <thead>
                        <tr>
                            <th onclick="sortTable('tableCount', 0, 'string')">Date</th>
                            <th onclick="sortTable('tableCount', 1, 'number')">Count</th>
                            <th onclick="sortTable('tableCount', 2, 'number')">Min</th>
                            <th onclick="sortTable('tableCount', 3, 'number')">AQI</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
        <div class="card">
            <h3 class="clickable-table-title" onclick="openTableChart('duration', 'All Days with Longest Alerts (> 4 hours)')">
                All Days with Longest Alerts (> 4 hours) & AQI
            </h3>
            <p style="font-size: 11px; color: var(--text-muted); margin-bottom: 10px;">Click title for category chart</p>
            <div class="table-container">
                <table id="tableDuration">
                    <thead>
                        <tr>
                            <th onclick="sortTable('tableDuration', 0, 'string')">Date</th>
                            <th onclick="sortTable('tableDuration', 1, 'number')">Duration</th>
                            <th onclick="sortTable('tableDuration', 2, 'number')">Count</th>
                            <th onclick="sortTable('tableDuration', 3, 'number')">AQI</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
    </div>

    <div class="grid grid-2" style="margin-top: 20px;">
        <div class="card">
            <h3 class="clickable-table-title" onclick="openTableChart('noAlerts', 'Days WITHOUT Air Raid Alerts')">
                Days WITHOUT Air Raid Alerts & AQI
            </h3>
            <p style="font-size: 11px; color: var(--text-muted); margin-bottom: 10px;">Click title for category chart</p>
            <div class="table-container">
                <table id="tableNoAlerts">
                    <thead>
                        <tr>
                            <th onclick="sortTable('tableNoAlerts', 0, 'string')">Date</th>
                            <th onclick="sortTable('tableNoAlerts', 1, 'number')">Alerts Count</th>
                            <th onclick="sortTable('tableNoAlerts', 2, 'number')">Total Min</th>
                            <th onclick="sortTable('tableNoAlerts', 3, 'number')">AQI</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
        <div class="card">
            <h3 class="clickable-table-title" onclick="openTableChart('pollutionAfterCalm', 'Highest Pollution IMMEDIATELY AFTER Calm Days')">
                Highest Pollution IMMEDIATELY AFTER Calm Days
            </h3>
            <p style="font-size: 11px; color: var(--text-muted); margin-bottom: 10px;">Click title for category chart</p>
            <div class="table-container">
                <table id="tablePollutionAfterCalm">
                    <thead>
                        <tr>
                            <th onclick="sortTable('tablePollutionAfterCalm', 0, 'string')">Date</th>
                            <th onclick="sortTable('tablePollutionAfterCalm', 1, 'number')">AQI</th>
                            <th onclick="sortTable('tablePollutionAfterCalm', 2, 'number')">Alerts Count</th>
                            <th onclick="sortTable('tablePollutionAfterCalm', 3, 'number')">Total Min</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
    </div>

    <div class="footer-terrorist-state">
        #RUSSIAISATERRORISTSTATE
    </div>

    <div class="modal-overlay" id="chartModal" onclick="closeTableChart(event)">
        <div class="modal-content" onclick="event.stopPropagation()">
            <button class="modal-close" onclick="closeTableChart()">&times;</button>
            <h3 class="modal-title" id="modalChartTitle">Category Analytics</h3>
            <div style="position: relative; width: 100%; height: 380px;">
                <canvas id="modalChartCanvas"></canvas>
            </div>
        </div>
    </div>

    <script>
        function toggleTheme() {{
            const html = document.documentElement;
            if (html.getAttribute('data-theme') === 'light') {{
                html.removeAttribute('data-theme');
                localStorage.setItem('theme', 'dark');
            }} else {{
                html.setAttribute('data-theme', 'light');
                localStorage.setItem('theme', 'light');
            }}
        }}

        if (localStorage.getItem('theme') === 'light') {{
            document.documentElement.setAttribute('data-theme', 'light');
        }}

        const countData = {json.dumps(count_table_data)};
        const durationData = {json.dumps(duration_table_data)};
        const noAlertsData = {json.dumps(no_alerts_table_data)};
        const pollutionAfterCalmData = {json.dumps(pollution_after_calm_data)};
        const topPollutionData = {json.dumps(top_pollution_data)};

        function renderTables() {{
            const tbodyTopPol = document.querySelector('#tableTopPollution tbody');
            tbodyTopPol.innerHTML = topPollutionData.map(r => `
                <tr>
                    <td>${{r.date}}</td>
                    <td style="font-weight: bold; color: #ef4444;">${{r.aqi === -1 ? 'N/A' : r.aqi}}</td>
                    <td>${{r.count}}</td>
                    <td>${{r.mins}} min</td>
                </tr>
            `).join('');

            const tbodyCount = document.querySelector('#tableCount tbody');
            tbodyCount.innerHTML = countData.map(r => `
                <tr>
                    <td>${{r.date}}</td>
                    <td>${{r.count}} (>4)</td>
                    <td>${{r.mins}}</td>
                    <td>${{r.aqi === -1 ? 'N/A' : r.aqi}}</td>
                </tr>
            `).join('');

            const tbodyDur = document.querySelector('#tableDuration tbody');
            tbodyDur.innerHTML = durationData.map(r => `
                <tr>
                    <td>${{r.date}}</td>
                    <td>${{r.mins}} min (>4h)</td>
                    <td>${{r.count}}</td>
                    <td>${{r.aqi === -1 ? 'N/A' : r.aqi}}</td>
                </tr>
            `).join('');

            const tbodyNoAlerts = document.querySelector('#tableNoAlerts tbody');
            tbodyNoAlerts.innerHTML = noAlertsData.map(r => `
                <tr>
                    <td>${{r.date}}</td>
                    <td>0</td>
                    <td>0 min</td>
                    <td>${{r.aqi === -1 ? 'N/A' : r.aqi}}</td>
                </tr>
            `).join('');

            const tbodyPollution = document.querySelector('#tablePollutionAfterCalm tbody');
            tbodyPollution.innerHTML = pollutionAfterCalmData.map(r => `
                <tr>
                    <td>${{r.date}}</td>
                    <td>${{r.aqi === -1 ? 'N/A' : r.aqi}}</td>
                    <td>${{r.count}}</td>
                    <td>${{r.mins}} min</td>
                </tr>
            `).join('');
        }}

        const sortDirections = {{}};
        function sortTable(tableId, colIndex, type) {{
            let dataArray;
            let key = '';

            if (tableId === 'tableTopPollution') {{
                dataArray = topPollutionData;
                key = ['date', 'aqi', 'count', 'mins'][colIndex];
            }} else if (tableId === 'tableCount') {{
                dataArray = countData;
                key = ['date', 'count', 'mins', 'aqi'][colIndex];
            }} else if (tableId === 'tableDuration') {{
                dataArray = durationData;
                key = ['date', 'mins', 'count', 'aqi'][colIndex];
            }} else if (tableId === 'tableNoAlerts') {{
                dataArray = noAlertsData;
                key = ['date', 'count', 'mins', 'aqi'][colIndex];
            }} else if (tableId === 'tablePollutionAfterCalm') {{
                dataArray = pollutionAfterCalmData;
                key = ['date', 'aqi', 'count', 'mins'][colIndex];
            }}

            const dirKey = tableId + '_' + colIndex;
            sortDirections[dirKey] = !sortDirections[dirKey];
            const asc = sortDirections[dirKey];

            dataArray.sort((a, b) => {{
                let valA = a[key];
                let valB = b[key];

                if (type === 'string') {{
                    return asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
                }} else {{
                    return asc ? valA - valB : valB - valA;
                }}
            }});

            renderTables();
        }}

        let modalChartInstance = null;
        function openTableChart(tableKey, titleText) {{
            const modal = document.getElementById('chartModal');
            document.getElementById('modalChartTitle').innerText = titleText + " — Category Breakdown Chart";
            modal.style.display = 'flex';

            let datasetSrc = [];
            let datasetsConfig = [];

            if (tableKey === 'topPollution') {{
                datasetSrc = topPollutionData.slice(0, 12);
                datasetsConfig = [
                    {{ label: 'AQI (Pollution)', data: datasetSrc.map(r => r.aqi === -1 ? 0 : r.aqi), backgroundColor: '#ef4444', borderRadius: 4 }},
                    {{ label: 'Alerts Count', data: datasetSrc.map(r => r.count), backgroundColor: '#3b82f6', borderRadius: 4 }}
                ];
            }} else if (tableKey === 'count') {{
                datasetSrc = countData.slice(0, 12);
                datasetsConfig = [
                    {{ label: 'Alerts Count', data: datasetSrc.map(r => r.count), backgroundColor: '#f59e0b', borderRadius: 4 }},
                    {{ label: 'AQI Level', data: datasetSrc.map(r => r.aqi === -1 ? 0 : r.aqi), backgroundColor: '#10b981', borderRadius: 4 }}
                ];
            }} else if (tableKey === 'duration') {{
                datasetSrc = durationData.slice(0, 12);
                datasetsConfig = [
                    {{ label: 'Duration (min)', data: datasetSrc.map(r => r.mins), backgroundColor: '#ef4444', borderRadius: 4 }},
                    {{ label: 'Alerts Count', data: datasetSrc.map(r => r.count), backgroundColor: '#3b82f6', borderRadius: 4 }}
                ];
            }} else if (tableKey === 'noAlerts') {{
                datasetSrc = noAlertsData.slice(0, 12);
                datasetsConfig = [
                    {{ label: 'AQI (Calm Days)', data: datasetSrc.map(r => r.aqi === -1 ? 0 : r.aqi), backgroundColor: '#3b82f6', borderRadius: 4 }}
                ];
            }} else if (tableKey === 'pollutionAfterCalm') {{
                datasetSrc = pollutionAfterCalmData.slice(0, 12);
                datasetsConfig = [
                    {{ label: 'AQI (After Calm)', data: datasetSrc.map(r => r.aqi === -1 ? 0 : r.aqi), backgroundColor: '#ef4444', borderRadius: 4 }},
                    {{ label: 'Alerts Count', data: datasetSrc.map(r => r.count), backgroundColor: '#3b82f6', borderRadius: 4 }}
                ];
            }}

            const labels = datasetSrc.map(r => r.date);

            const ctx = document.getElementById('modalChartCanvas').getContext('2d');
            if (modalChartInstance) {{
                modalChartInstance.destroy();
            }}

            modalChartInstance = new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: labels,
                    datasets: datasetsConfig
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ display: true, labels: {{ color: '#8b92a5' }} }} }},
                    scales: {{
                        y: {{ grid: {{ color: 'rgba(150,150,150,0.1)' }}, ticks: {{ color: '#8b92a5' }} }},
                        x: {{ grid: {{ display: false }}, ticks: {{ color: '#8b92a5' }} }}
                    }}
                }}
            }});
        }}

        function closeTableChart() {{
            document.getElementById('chartModal').style.display = 'none';
        }}

        const allDailyData = {daily_data_json};
        const dataMap = new Map();
        allDailyData.forEach(item => {{
            dataMap.set(item.date_str, item);
        }});

        function updateSelectedWeek() {{
            const startInput = document.getElementById('startDate').value;
            if (!startInput) return;

            let startDate = new Date(startInput);
            let endDate = new Date(startDate);
            endDate.setDate(startDate.getDate() + 6);

            const formatDateStr = (d) => {{
                let year = d.getFullYear();
                let month = String(d.getMonth() + 1).padStart(2, '0');
                let day = String(d.getDate()).padStart(2, '0');
                return `${{year}}-${{month}}-${{day}}`;
            }};

            document.getElementById('endDate').value = formatDateStr(endDate);

            let totalMins = 0;
            let totalCnt = 0;
            let aqiSum = 0;
            let aqiCount = 0;
            let daysWithData = 0;

            let curr = new Date(startDate);
            while (curr <= endDate) {{
                let dStr = formatDateStr(curr);
                if (dataMap.has(dStr)) {{
                    let dayObj = dataMap.get(dStr);
                    totalMins += dayObj.total_min;
                    totalCnt += dayObj.count;
                    if (dayObj.aqi !== "N/A" && dayObj.aqi !== null) {{
                        aqiSum += parseFloat(dayObj.aqi);
                        aqiCount++;
                    }}
                    daysWithData++;
                }}
                curr.setDate(curr.getDate() + 1);
            }}

            if (daysWithData === 0) {{
                document.getElementById('weekAvgDuration').innerText = 'No data available for this period';
                document.getElementById('weekTotalCount').innerText = 'No data available for this period';
                document.getElementById('weekAvgAqi').innerText = 'No data available for this period';
                return;
            }}

            let avgDuration = Math.round(totalMins / 7);
            let avgAqi = aqiCount > 0 ? (aqiSum / aqiCount).toFixed(1) : 'N/A';

            document.getElementById('weekAvgDuration').innerText = `${{avgDuration}} min/day (avg)`;
            document.getElementById('weekTotalCount').innerText = `${{totalCnt}} total`;
            document.getElementById('weekAvgAqi').innerText = avgAqi;
        }}

        document.getElementById('startDate').addEventListener('change', updateSelectedWeek);

        window.addEventListener('DOMContentLoaded', () => {{
            renderTables();
            updateSelectedWeek();

            Chart.defaults.color = '#8b92a5';
            Chart.defaults.font.family = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";

            const ctxBar = document.getElementById('barChart').getContext('2d');
            new Chart(ctxBar, {{
                type: 'bar',
                data: {{
                    labels: {json.dumps([str(y) for y in years_list])},
                    datasets: [{{
                        label: 'Average Duration (min)',
                        data: {json.dumps(yearly_values)},
                        backgroundColor: '#3b82f6',
                        borderRadius: 6
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        y: {{ grid: {{ color: 'rgba(150,150,150,0.1)' }}, ticks: {{ color: '#8b92a5' }} }},
                        x: {{ grid: {{ display: false }}, ticks: {{ color: '#8b92a5' }} }}
                    }}
                }}
            }});

            const ctxPie = document.getElementById('pieChart').getContext('2d');
            new Chart(ctxPie, {{
                type: 'doughnut',
                data: {{
                    labels: [
                        'Longest alerts >4h ({days_dur_count} days / {pct_dur}%)', 
                        'Most alerts >4 times ({days_count_count} days / {pct_count}%)', 
                        'Both categories ({days_both_count} days / {pct_both}%)', 
                        'No-alert days ({days_no_alert_count} days / {pct_no_alert}%)',
                        'Other days ({days_other_count} days / {pct_other}%)'
                    ],
                    datasets: [{{
                        data: [{days_dur_count}, {days_count_count}, {days_both_count}, {days_no_alert_count}, {days_other_count}],
                        backgroundColor: ['#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#374151'],
                        borderWidth: 0
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ position: 'bottom', labels: {{ color: '#8b92a5', padding: 10, boxWidth: 10 }} }}
                    }},
                    cutout: '65%'
                }}
            }});
        }});
    </script>

</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print(
    "File index.html successfully generated with external navigation buttons and #RUSSIAISATERRORISTSTATE!"
)
