import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go

# 1. Налаштування сторінки та кастомний CSS для темної теми
st.set_page_config(page_title="Дашборд: Тривоги та Забруднення", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
        /* Глибокий темний фон як на скриншоті */
        .stApp {
            background-color: #0f111a;
            color: #ffffff;
        }
        /* Стилізація метрик (карток) */
        div[data-testid="metric-container"] {
            background-color: #1e2130;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.05);
        }
        div[data-testid="metric-container"] label {
            color: #8b92a5 !important;
            font-size: 14px !important;
            text-transform: uppercase;
        }
        div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
            color: #ffffff;
            font-size: 32px !important;
            font-weight: bold;
        }
        /* Стилізація заголовків */
        h1, h2, h3 {
            color: #ffffff !important;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        /* Таблиці */
        .dataframe {
            background-color: #1e2130 !important;
            color: #ffffff !important;
        }
        .dataframe th {
            background-color: #2a2e42 !important;
            color: #8b92a5 !important;
            border: none !important;
        }
        .dataframe td {
            border-bottom: 1px solid rgba(255,255,255,0.05) !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("Аналітика Повітряних Тривог та Якості Повітря")

# 2. Завантаження та обробка даних
@st.cache_data
def load_data():
    with open('airAlert.json', 'r', encoding='utf-8') as f:
        alerts = json.load(f)
    df_alerts = pd.DataFrame(alerts)
    df_alerts['dateTimeStart'] = pd.to_datetime(df_alerts['dateTimeStart'])
    df_alerts['dateTimeEnd'] = pd.to_datetime(df_alerts['dateTimeEnd'])
    df_alerts = df_alerts.dropna(subset=['dateTimeStart', 'dateTimeEnd'])
    df_alerts['duration_minutes'] = (df_alerts['dateTimeEnd'] - df_alerts['dateTimeStart']).dt.total_seconds() / 60
    df_alerts['year'] = df_alerts['dateTimeStart'].dt.year
    df_alerts['date'] = df_alerts['dateTimeStart'].dt.date
    
    df_eco = pd.read_csv('saveecobot_city_2_hourly.csv', low_memory=False)
    df_eco['logged_at'] = pd.to_datetime(df_eco['logged_at'])
    df_eco['date'] = df_eco['logged_at'].dt.date
    df_aqi = df_eco[df_eco['phenomenon'] == 'aqi']
    daily_aqi = df_aqi.groupby('date')['value'].mean().reset_index()
    
    return df_alerts, daily_aqi

df_alerts, daily_aqi = load_data()

# 3. Аналітика забруднень (Метрики зверху)
start_pre, end_pre = pd.to_datetime('2022-02-17').date(), pd.to_datetime('2022-02-23').date()
start_post, end_post = pd.to_datetime('2022-02-24').date(), pd.to_datetime('2022-03-02').date()

aqi_pre = daily_aqi[(daily_aqi['date'] >= start_pre) & (daily_aqi['date'] <= end_pre)]['value'].mean()
aqi_post = daily_aqi[(daily_aqi['date'] >= start_post) & (daily_aqi['date'] <= end_post)]['value'].mean()

st.markdown("### 1. Рівень забруднення повітря (AQI)")
col1, col2, col3 = st.columns(3)
col1.metric("AQI До (17-23 лют 2022)", f"{aqi_pre:.1f}")
col2.metric("AQI Після (24 лют-2 бер 2022)", f"{aqi_post:.1f}")
col3.metric("Різниця AQI", f"{aqi_post - aqi_pre:.1f}", delta=f"{aqi_post - aqi_pre:.1f}", delta_color="inverse")

st.markdown("---")

# 4. Графіки
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.markdown("### Середня тривалість тривог за роками")
    avg_duration_yr = df_alerts[df_alerts['year'] >= 2022].groupby('year')['duration_minutes'].mean().round(1).reset_index()
    
    fig_bar = px.bar(avg_duration_yr, x='year', y='duration_minutes', text='duration_minutes')
    fig_bar.update_traces(marker_color='#3b82f6', marker_line_width=0, textposition='outside', textfont_color='#ffffff')
    fig_bar.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='#8b92a5',
        xaxis=dict(showgrid=False, title="Рік"),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="Тривалість (хв)"),
        margin=dict(l=0, r=0, t=30, b=0)
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with col_chart2:
    st.markdown("### Розподіл рекордних днів (Топ 5%)")
    daily_alerts = df_alerts.groupby('date').agg(
        alert_count=('uid', 'count'),
        total_duration=('duration_minutes', 'sum')
    ).reset_index()

    total_alert_days = len(daily_alerts)
    top_n = max(int(total_alert_days * 0.05), 10)

    set_longest = set(daily_alerts.nlargest(top_n, 'total_duration')['date'])
    set_most = set(daily_alerts.nlargest(top_n, 'alert_count')['date'])
    days_both = set_longest.intersection(set_most)
    
    sizes = [
        len(set_longest - days_both),
        len(set_most - days_both),
        len(days_both),
        total_alert_days - len(set_longest.union(set_most))
    ]
    labels = ['Найдовші (Топ 5%)', 'Найбільше (Топ 5%)', 'Обидві категорії', 'Інші дні']
    colors = ['#ef4444', '#f59e0b', '#10b981', '#374151']

    fig_pie = go.Figure(data=[go.Pie(labels=labels, values=sizes, hole=.7, marker_colors=colors)])
    fig_pie.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='#8b92a5',
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig_pie, use_container_width=True)

st.markdown("---")

# 5. Таблиці зі співставленням
col_t1, col_t2 = st.columns(2)

def format_aqi(val):
    return f"{val:.1f}" if pd.notnull(val) and val > 0 else "Немає"

top_count = daily_alerts.nlargest(10, 'alert_count')
top_duration = daily_alerts.nlargest(10, 'total_duration')

merged_count = pd.merge(top_count, daily_aqi, on='date', how='left')
merged_count['value'] = merged_count['value'].apply(format_aqi)
merged_count = merged_count.rename(columns={'date': 'Дата', 'alert_count': 'К-ть тривог', 'total_duration': 'Тривалість (хв)', 'value': 'AQI'})

merged_duration = pd.merge(top_duration, daily_aqi, on='date', how='left')
merged_duration['value'] = merged_duration['value'].apply(format_aqi)
merged_duration = merged_duration.rename(columns={'date': 'Дата', 'total_duration': 'Тривалість (хв)', 'alert_count': 'К-ть тривог', 'value': 'AQI'})

with col_t1:
    st.markdown("### Дні з найбільшою кількістю тривог")
    st.dataframe(merged_count, hide_index=True, use_container_width=True)

with col_t2:
    st.markdown("### Дні з найдовшими тривогами")
    st.dataframe(merged_duration, hide_index=True, use_container_width=True)
