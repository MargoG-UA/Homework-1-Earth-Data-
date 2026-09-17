import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Аналітика", layout="wide")

# ==========================================
# ⚙️ БЛОК НАЛАШТУВАНЬ (ЗМІНИТИ НАЗВИ ТУТ)
# ==========================================
# Назви колонок у файлі airAlert.json
COL_ALERT_START = 'started_at'  
COL_ALERT_END = 'finished_at'

# Назви колонок у файлі saveecobot_city_2_hourly.csv
COL_ECO_DATE = 'timestamp'
COL_ECO_VALUE = 'value'
# ==========================================

st.title("🛡️ Аналітика: Повітряні тривоги та якість повітря")

# --- ФУНКЦІЯ ЗАВАНТАЖЕННЯ ---
@st.cache_data
def load_and_prep_data():
    alerts = pd.read_json('airAlert.json')
    eco = pd.read_csv('saveecobot_city_2_hourly.csv')
    return alerts, eco

# --- СПРОБА ЗАВАНТАЖЕННЯ ТА ПАРСИНГУ ---
try:
    alerts_raw, eco_raw = load_and_prep_data()
except Exception as e:
    st.error(f"Не вдалося прочитати файли. Перевір, чи вони лежать у тій самій папці. Помилка: {e}")
    st.stop()

# Перевірка наявності колонок
missing_alert_cols = [col for col in [COL_ALERT_START, COL_ALERT_END] if col not in alerts_raw.columns]
missing_eco_cols = [col for col in [COL_ECO_DATE, COL_ECO_VALUE] if col not in eco_raw.columns]

if missing_alert_cols or missing_eco_cols:
    st.error("Помилка: Неправильні назви колонок у блоці налаштувань.")
    col1, col2 = st.columns(2)
    with col1:
        st.warning("Реальні колонки в airAlert.json:")
        st.write(alerts_raw.columns.tolist())
        st.dataframe(alerts_raw.head(2))
    with col2:
        st.warning("Реальні колонки в saveecobot.csv:")
        st.write(eco_raw.columns.tolist())
        st.dataframe(eco_raw.head(2))
    st.stop()

# Якщо все ок - парсимо дати
try:
    alerts = alerts_raw.copy()
    eco = eco_raw.copy()
    
    alerts['start'] = pd.to_datetime(alerts[COL_ALERT_START], errors='coerce')
    alerts['end'] = pd.to_datetime(alerts[COL_ALERT_END], errors='coerce')
    alerts = alerts.dropna(subset=['start', 'end']) # Викидаємо биті рядки
    alerts['duration_minutes'] = (alerts['end'] - alerts['start']).dt.total_seconds() / 60
    alerts['date'] = alerts['start'].dt.date
    alerts['year'] = alerts['start'].dt.year

    eco['date_time'] = pd.to_datetime(eco[COL_ECO_DATE], errors='coerce')
    eco = eco.dropna(subset=['date_time', COL_ECO_VALUE])
    eco['date'] = eco['date_time'].dt.date
except Exception as e:
    st.error(f"Помилка при перетворенні дат. Можливо, нестандартний формат. Деталі: {e}")
    st.stop()

# --- ОБРОБКА ТА ВІЗУАЛІЗАЦІЯ ---
st.markdown("---")

# 1. Середня тривалість по роках (з 2022)
st.subheader("📊 Середня тривалість тривоги по роках (з 2022)")
alerts_from_2022 = alerts[alerts['year'] >= 2022]
if not alerts_from_2022.empty:
    avg_duration = alerts_from_2022.groupby('year')['duration_minutes'].mean().reset_index()
    cols = st.columns(len(avg_duration))
    for i, row in avg_duration.iterrows():
        cols[i].metric(label=f"Рік {int(row['year'])}", value=f"{row['duration_minutes']:.1f} хв")
else:
    st.info("Немає даних про тривоги починаючи з 2022 року.")

st.markdown("---")

# 2. Топи та кругові діаграми
daily_alerts = alerts.groupby('date').agg(
    alert_count=('start', 'count'),
    total_duration=('duration_minutes', 'sum')
).reset_index()

top_count_days = daily_alerts.nlargest(10, 'alert_count')
top_duration_days = daily_alerts.nlargest(10, 'total_duration')

st.subheader("🍩 Відсоткове співвідношення екстремальних днів (Топ-10)")
col1, col2 = st.columns(2)

total_days = len(daily_alerts)
if total_days > 10:
    with col1:
        fig1 = px.pie(
            values=[10, total_days - 10], 
            names=['Топ-10 днів за кількістю', 'Інші дні'],
            hole=0.4, color_discrete_sequence=['#ff9900', '#3366cc']
        )
        st.plotly_chart(fig1, use_container_width=True)
    with col2:
        fig2 = px.pie(
            values=[10, total_days - 10], 
            names=['Топ-10 днів за тривалістю', 'Інші дні'],
            hole=0.4, color_discrete_sequence=['#00cc96', '#3366cc']
        )
        st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("Недостатньо днів для побудови діаграми відсотка (менше 10).")

st.markdown("---")

# 3. Екологія до та після (лютий-березень 2022)
st.subheader("🌫️ Забруднення до і після 24.02.2022")
pre_invasion = eco[(eco['date_time'] >= '2022-02-17') & (eco['date_time'] < '2022-02-24')]
post_invasion = eco[(eco['date_time'] >= '2022-03-01') & (eco['date_time'] < '2022-03-08')]

if not pre_invasion.empty and not post_invasion.empty:
    pre_avg = pre_invasion[COL_ECO_VALUE].mean()
    post_avg = post_invasion[COL_ECO_VALUE].mean()
    
    ec1, ec2, ec3 = st.columns(3)
    ec1.metric("Тиждень ДО (17-23 лют)", f"{pre_avg:.2f}")
    ec2.metric("Тиждень ПІСЛЯ (01-07 бер)", f"{post_avg:.2f}", delta=f"{post_avg - pre_avg:.2f}", delta_color="inverse")
else:
    st.warning("Не знайдено даних про забруднення за лютий-березень 2022 року.")

st.markdown("---")

# 4. Співставлення
st.subheader("🔍 Зв'язок: Тривоги та рівень забруднення")
daily_eco = eco.groupby('date')[COL_ECO_VALUE].mean().reset_index()

merged_count = pd.merge(top_count_days, daily_eco, on='date', how='left').rename(
    columns={'date': 'Дата', 'alert_count': 'К-сть тривог', 'total_duration': 'Тривалість (хв)', COL_ECO_VALUE: 'Середнє забруднення'}
)
merged_duration = pd.merge(top_duration_days, daily_eco, on='date', how='left').rename(
    columns={'date': 'Дата', 'alert_count': 'К-сть тривог', 'total_duration': 'Тривалість (хв)', COL_ECO_VALUE: 'Середнє забруднення'}
)

tab1, tab2 = st.tabs(["Дні з найчастішими тривогами", "Дні з найдовшими тривогами"])
with tab1:
    st.dataframe(merged_count, use_container_width=True)
with tab2:
    st.dataframe(merged_duration, use_container_width=True)
