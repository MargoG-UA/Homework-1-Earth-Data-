import pandas as pd
import json

# 1. Завантаження даних
with open('airAlert.json', 'r', encoding='utf-8') as f:
    alerts = json.load(f)
df_alerts = pd.DataFrame(alerts)
df_alerts['dateTimeStart'] = pd.to_datetime(df_alerts['dateTimeStart'])
df_alerts['dateTimeEnd'] = pd.to_datetime(df_alerts['dateTimeEnd'])
df_alerts = df_alerts.dropna(subset=['dateTimeStart', 'dateTimeEnd'])
df_alerts['duration_minutes'] = (df_alerts['dateTimeEnd'] - df_alerts['dateTimeStart']).dt.total_seconds() / 60
df_alerts['year'] = df_alerts['dateTimeStart'].dt.year
df_alerts['date'] = df_alerts['dateTimeStart'].dt.date

avg_duration_yr = df_alerts[df_alerts['year'] >= 2022].groupby('year')['duration_minutes'].mean().round(1)
daily_alerts = df_alerts.groupby('date').agg(alert_count=('uid', 'count'), total_duration=('duration_minutes', 'sum')).reset_index()

total_alert_days = len(daily_alerts)
top_n = max(int(total_alert_days * 0.05), 10)
set_longest = set(daily_alerts.nlargest(top_n, 'total_duration')['date'])
set_most = set(daily_alerts.nlargest(top_n, 'alert_count')['date'])
days_both = set_longest.intersection(set_most)
days_only_longest = set_longest - days_both
days_only_most = set_most - days_both
days_other = total_alert_days - len(set_longest.union(set_most))

df_eco = pd.read_csv('saveecobot_city_2_hourly.csv', low_memory=False)
df_eco['logged_at'] = pd.to_datetime(df_eco['logged_at'])
df_eco['date'] = df_eco['logged_at'].dt.date
df_aqi = df_eco[df_eco['phenomenon'] == 'aqi']
daily_aqi = df_aqi.groupby('date')['value'].mean().reset_index()

start_pre, end_pre = pd.to_datetime('2022-02-17').date(), pd.to_datetime('2022-02-23').date()
start_post, end_post = pd.to_datetime('2022-02-24').date(), pd.to_datetime('2022-03-02').date()
aqi_pre = daily_aqi[(daily_aqi['date'] >= start_pre) & (daily_aqi['date'] <= end_pre)]['value'].mean()
aqi_post = daily_aqi[(daily_aqi['date'] >= start_post) & (daily_aqi['date'] <= end_post)]['value'].mean()

merged_count = pd.merge(daily_alerts.nlargest(10, 'alert_count'), daily_aqi, on='date', how='left').fillna(0)
merged_duration = pd.merge(daily_alerts.nlargest(10, 'total_duration'), daily_aqi, on='date', how='left').fillna(0)

# 2. Формування HTML
def format_aqi(val): return f"{val:.1f}" if val > 0 else "Немає даних"

merged_count_rows = "".join([f"<tr><td>{row['date']}</td><td>{row['alert_count']}</td><td>{row['total_duration']:.0f}</td><td>{format_aqi(row['value'])}</td></tr>" for _, row in merged_count.iterrows()])
merged_duration_rows = "".join([f"<tr><td>{row['date']}</td><td>{row['total_duration']:.0f}</td><td>{row['alert_count']}</td><td>{format_aqi(row['value'])}</td></tr>" for _, row in merged_duration.iterrows()])

html = f"""<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Air Alert & AQI Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-color: #0f111a;
            --panel-bg: #1e2130;
            --text-main: #ffffff;
            --text-muted: #8b92a5;
        }}
        body {{ margin: 0; padding: 30px; background-color: var(--bg-color); color: var(--text-main); font-family: sans-serif; }}
        .header {{ margin-bottom: 30px; }}
        .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 20px; }}
        .card {{ background: var(--panel-bg); border-radius: 12px; padding: 24px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.05); }}
        .card h3 {{ margin: 0 0 15px; font-size: 14px; text-transform: uppercase; color: var(--text-main); }}
        .card .value {{ font-size: 32px; font-weight: bold; color: var(--text-main); }}
        .grid-2 {{ grid-template-columns: repeat(2, 1fr); }}
        .grid-3 {{ grid-template-columns: repeat(3, 1fr); }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ text-align: left; padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.05); color: var(--text-main); }}
        th {{ text-transform: uppercase; font-size: 12px; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="header"><h1>Дашборд: Тривоги та Забруднення</h1></div>
    <div class="grid grid-3">
        <div class="card"><h3>AQI (17-23 лют 2022)</h3><div class="value">{aqi_pre:.1f}</div></div>
        <div class="card"><h3>AQI (24 лют-2 бер 2022)</h3><div class="value">{aqi_post:.1f}</div></div>
        <div class="card"><h3>Різниця AQI</h3><div class="value">+{aqi_post - aqi_pre:.1f}</div></div>
    </div>
    <div class="grid grid-2">
        <div class="card"><h3>Середня тривалість (хв)</h3><canvas id="barChart"></canvas></div>
        <div class="card"><h3>Розподіл рекордних днів</h3><canvas id="pieChart"></canvas></div>
    </div>
    <div class="grid grid-2">
        <div class="card"><h3>Найбільше тривог</h3>
            <table><tr><th>Дата</th><th>К-ть</th><th>Хвилини</th><th>AQI</th></tr>{merged_count_rows}</table>
        </div>
        <div class="card"><h3>Найдовші тривоги</h3>
            <table><tr><th>Дата</th><th>Хвилини</th><th>К-ть</th><th>AQI</th></tr>{merged_duration_rows}</table>
        </div>
    </div>
<script>
    Chart.defaults.color = '#ffffff';
    new Chart(document.getElementById('barChart'), {{
        type: 'bar',
        data: {{ labels: {list(avg_duration_yr.index)}, datasets: [{{ label: 'Хв', data: {list(avg_duration_yr.values)}, backgroundColor: '#3b82f6' }}] }},
        options: {{ scales: {{ y: {{ ticks: {{ color: '#ffffff' }} }}, x: {{ ticks: {{ color: '#ffffff' }} }} }} }}
    }});
    new Chart(document.getElementById('pieChart'), {{
        type: 'doughnut',
        data: {{ labels: ['Найдовші', 'Найбільше', 'Обидві', 'Інші'], datasets: [{{ data: [{len(days_only_longest)}, {len(days_only_most)}, {len(days_both)}, {days_other}], backgroundColor: ['#ef4444', '#f59e0b', '#10b981', '#374151'] }}] }},
        options: {{ plugins: {{ legend: {{ labels: {{ color: '#ffffff' }} }} }} }}
    }});
</script>
</body>
</html>
"""
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Готово! index.html створено.")