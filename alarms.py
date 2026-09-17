import streamlit as st
import pandas as pd
import json
import plotly.express as px

# Конфігурація сторінки
st.set_page_config(page_title="Дашборд: Тривоги та Забруднення", layout="wide")
st.title("Аналітика Повітряних Тривог та Якості Повітря")

# 1. Завантаження та обробка даних
@st.cache_data
def load_data():
    # Дані тривог
    with open('airAlert.json', 'r', encoding='utf-8') as f:
        alerts = json.load(f)
    df_alerts = pd.DataFrame(alerts)
    df_alerts['dateTimeStart'] = pd.to_datetime(df_alerts['dateTimeStart'])
    df_alerts['dateTimeEnd'] = pd.to_datetime(df_alerts['dateTimeEnd'])
    df_alerts = df_alerts.dropna(subset=['dateTimeStart', 'dateTimeEnd'])
    df_alerts['duration_minutes'] = (df_alerts['dateTimeEnd'] - df_alerts['dateTimeStart']).dt.total_seconds() / 60
    df_alerts['year'] = df_alerts['dateTimeStart'].dt.year
    df_alerts['date'] = df_alerts['dateTimeStart'].dt.date
    
    # Дані забруднень
    df_eco = pd.read_csv('saveecobot_city_2_hourly.csv', low_memory=False)
    df_eco['logged_at'] = pd.to_datetime(df_eco['logged_at'])
    df_eco['date'] = df_eco['logged_at'].dt.date
    df_aqi = df_eco[df_eco['phenomenon'] == 'aqi']
    daily_aqi = df_aqi.groupby('date')['value'].mean().reset_index()
    
    return df_alerts, daily_aqi

df_alerts, daily_aqi = load_data()

# 2. Аналітика Тривог
st.header("1. Середня тривалість тривог за роками (з 2022)")
avg_duration_yr = df_alerts[df_alerts['year'] >= 2022].groupby('year')['duration_minutes'].mean().round(1).reset_index()
fig_years = px.bar(avg_duration_yr, x='year', y='duration_minutes', text='duration_minutes',
                   labels={'year': 'Рік', 'duration_minutes': 'Середня тривалість (хв)'}, 
                   color_discrete_sequence=['#3498db'])
st.plotly_chart(fig_years, use_container_width=True)

# 3. Аналіз рекордних днів та кругова діаграма
st.header("2. Розподіл тривожних днів")
daily_alerts = df_alerts.groupby('date').agg(
    alert_count=('uid', 'count'),
    total_duration=('duration_minutes', 'sum')
).reset_index()

total_alert_days = len(daily_alerts)
top_percent_count = max(int(total_alert_days * 0.05), 10) # Беремо Топ 5% днів

set_longest = set(daily_alerts.nlargest(top_percent_count, 'total_duration')['date'])
set_most = set(daily_alerts.nlargest(top_percent_count, 'alert_count')['date'])
days_both = set_longest.intersection(set_most)

sizes = [
    len(set_longest - days_both),
    len(set_most - days_both),
    len(days_both),
    total_alert_days - len(set_longest.union(set_most))
]
labels = ['Найдовші тривоги (Топ 5%)', 'Найбільше тривог (Топ 5%)', 'Обидві категорії', 'Інші дні']

fig_pie = px.pie(values=sizes, names=labels, hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
st.plotly_chart(fig_pie)

# 4. Рівень забруднень (До та після вторгнення)
st.header("3. Якість повітря: до та після повномасштабного вторгнення")
# Для порівняння беремо тиждень до (17-23 лютого) і тиждень після (24 лютого - 2 березня)
start_pre, end_pre = pd.to_datetime('2022-02-17').date(), pd.to_datetime('2022-02-23').date()
start_post, end_post = pd.to_datetime('2022-02-24').date(), pd.to_datetime('2022-03-02').date()

aqi_pre = daily_aqi[(daily_aqi['date'] >= start_pre) & (daily_aqi['date'] <= end_pre)]['value'].mean()
aqi_post = daily_aqi[(daily_aqi['date'] >= start_post) & (daily_aqi['date'] <= end_post)]['value'].mean()

col1, col2 = st.columns(2)
col1.metric("Середній AQI (17–23 Лют 2022)", f"{aqi_pre:.1f}")
col2.metric("Середній AQI (24 Лют–2 Бер 2022)", f"{aqi_post:.1f}", delta=f"{aqi_post - aqi_pre:.1f}", delta_color="inverse")

# 5. Співставлення: Тривоги + Якість повітря
st.header("4. Співставлення забруднення повітря у рекордні дні")
top_n = st.slider("Кількість днів для виведення в таблицю", 5, 20, 10)
top_count = daily_alerts.nlargest(top_n, 'alert_count')
top_duration = daily_alerts.nlargest(top_n, 'total_duration')

merged_count = pd.merge(top_count, daily_aqi, on='date', how='left').rename(
    columns={'date': 'Дата', 'alert_count': 'К-ть тривог', 'total_duration': 'Тривалість (хв)', 'value': 'Середній AQI'}
).fillna('Немає даних')

merged_duration = pd.merge(top_duration, daily_aqi, on='date', how='left').rename(
    columns={'date': 'Дата', 'total_duration': 'Тривалість (хв)', 'alert_count': 'К-ть тривог', 'value': 'Середній AQI'}
).fillna('Немає даних')

col_t1, col_t2 = st.columns(2)
with col_t1:
    st.subheader("Дні з найбільшою кількістю тривог")
    st.dataframe(merged_count, hide_index=True)

with col_t2:
    st.subheader("Дні з найдовшими тривогами")
    st.dataframe(merged_duration, hide_index=True)
