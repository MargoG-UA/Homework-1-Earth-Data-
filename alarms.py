import streamlit as st
import pandas as pd
import plotly.express as px

# Налаштування сторінки дашборду
st.set_page_config(page_title="Аналітика тривог та якості повітря", layout="wide", initial_sidebar_state="expanded")

# --- ЗАВАНТАЖЕННЯ ДАНИХ ---
@st.cache_data
def load_data():
    # Завантаження тривог
    alerts = pd.read_json('airAlert.json')
    # ПРИМІТКА: Заміни 'started_at' та 'finished_at' на реальні назви колонок з твого JSON
    alerts['start'] = pd.to_datetime(alerts['started_at'])
    alerts['end'] = pd.to_datetime(alerts['finished_at'])
    alerts['duration_minutes'] = (alerts['end'] - alerts['start']).dt.total_seconds() / 60
    alerts['date'] = alerts['start'].dt.date
    alerts['year'] = alerts['start'].dt.year
    
    # Завантаження забруднення
    eco = pd.read_csv('saveecobot_city_2_hourly.csv')
    # ПРИМІТКА: Заміни 'timestamp' та 'value' на реальні назви колонок з CSV
    eco['date_time'] = pd.to_datetime(eco['timestamp'])
    eco['date'] = eco['date_time'].dt.date
    
    return alerts, eco

try:
    alerts_df, eco_df = load_data()
except Exception as e:
    st.error(f"Помилка завантаження даних. Перевірте назви файлів та колонок. Деталі: {e}")
    st.stop()

# --- ОБРОБКА ДАНИХ ---
# 1. Середня тривалість за кожен рік з 2022
avg_duration_yearly = alerts_df[alerts_df['year'] >= 2022].groupby('year')['duration_minutes'].mean().reset_index()

# 2 & 3. Топ днів за кількістю та тривалістю
daily_alerts = alerts_df.groupby('date').agg(
    alert_count=('start', 'count'),
    total_duration=('duration_minutes', 'sum')
).reset_index()

top_count_days = daily_alerts.nlargest(10, 'alert_count')
top_duration_days = daily_alerts.nlargest(10, 'total_duration')

# 4. Підготовка даних для кругових діаграм
total_days = len(daily_alerts)
top_count_threshold = 10 # Вважаємо топ 10 днів "рекордними"
other_days_count = total_days - top_count_threshold

# 5 & 6. Забруднення до і після вторгнення
pre_invasion = eco_df[(eco_df['date_time'] >= '2022-02-17') & (eco_df['date_time'] < '2022-02-24')]
post_invasion = eco_df[(eco_df['date_time'] >= '2022-03-01') & (eco_df['date_time'] < '2022-03-08')] # Приклад: перший тиждень березня

pre_inv_avg = pre_invasion['value'].mean()
post_inv_avg = post_invasion['value'].mean()

# 7 & 8. Співставлення: Забруднення у дні найдовших та найчастіших тривог
daily_eco = eco_df.groupby('date')['value'].mean().reset_index()
merged_top_count = pd.merge(top_count_days, daily_eco, on='date', how='left')
merged_top_duration = pd.merge(top_duration_days, daily_eco, on='date', how='left')


# --- ІНТЕРФЕЙС ДАШБОРДУ ---
st.title("🛡️ Аналітична панель: Повітряні тривоги та екологія")
st.markdown("---")

# Секція 1: Базова статистика по роках
st.subheader("📊 Середня тривалість тривоги по роках (з 2022)")
cols = st.columns(len(avg_duration_yearly))
for i, row in avg_duration_yearly.iterrows():
    cols[i].metric(label=f"Рік {int(row['year'])}", value=f"{row['duration_minutes']:.1f} хв")

st.markdown("---")

# Секція 2: Колові діаграми
st.subheader("🍩 Відсоткове співвідношення екстремальних днів")
col1, col2 = st.columns(2)

with col1:
    fig_count = px.pie(
        values=[top_count_threshold, other_days_count], 
        names=['Дні з найбільшою кількістю тривог', 'Усі інші дні'],
        title="Співвідношення днів за кількістю тривог",
        hole=0.4, color_discrete_sequence=['#ff9900', '#3366cc']
    )
    st.plotly_chart(fig_count, use_container_width=True)

with col2:
    fig_duration = px.pie(
        values=[top_count_threshold, other_days_count], 
        names=['Дні з найдовшими тривогами', 'Усі інші дні'],
        title="Співвідношення днів за тривалістю тривог",
        hole=0.4, color_discrete_sequence=['#00cc96', '#3366cc']
    )
    st.plotly_chart(fig_duration, use_container_width=True)

st.markdown("---")

# Секція 3: Екологія до та після
st.subheader("🌫️ Вплив повномасштабного вторгнення на якість повітря")
ecol1, ecol2, ecol3 = st.columns(3)
ecol1.metric("Тиждень ДО (17.02 - 23.02)", f"{pre_inv_avg:.2f}")
ecol2.metric("Тиждень ПІСЛЯ (01.03 - 07.03)", f"{post_inv_avg:.2f}", delta=f"{post_inv_avg - pre_inv_avg:.2f}", delta_color="inverse")

st.markdown("---")

# Секція 4: Співставлення
st.subheader("🔍 Кореляція: Тривоги та рівень забруднення")
tab1, tab2 = st.tabs(["Дні з найчастішими тривогами", "Дні з найдовшими тривогами"])

with tab1:
    st.dataframe(
        merged_top_count.rename(columns={'date': 'Дата', 'alert_count': 'Кількість тривог', 'total_duration': 'Загальна тривалість (хв)', 'value': 'Рівень забруднення'}),
        use_container_width=True
    )

with tab2:
    st.dataframe(
        merged_top_duration.rename(columns={'date': 'Дата', 'alert_count': 'Кількість тривог', 'total_duration': 'Загальна тривалість (хв)', 'value': 'Рівень забруднення'}),
        use_container_width=True
    )
