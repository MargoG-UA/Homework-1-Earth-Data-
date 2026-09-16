import streamlit as st
import pandas as pd
import xarray as xr
import earthaccess
import re
import os
from datetime import datetime

# Налаштування сторінки
st.set_page_config(page_title="Аналіз якості повітря та тривог у Києві", layout="wide")
st.title("Аналіз ділянок Києва: Забруднення повітря та Повітряні тривоги")

# ==========================================
# 1. ЧИТАННЯ ДАНИХ ПРО ТРИВОГИ З JSON ФАЙЛУ
# ==========================================
@st.cache_data
def load_alarms_data():
    try:
        # Читаємо локальний файл airAlert.json напряму
        df = pd.read_json("airAlert.json")
        
        # Перевіряємо наявність потрібних колонок (бачили їх на вашому скріншоті)
        if 'dateTimeStart' in df.columns and 'dateTimeEnd' in df.columns:
            # Перетворюємо текст на формат дат
            df['dateTimeStart'] = pd.to_datetime(df['dateTimeStart'], errors='coerce')
            df['dateTimeEnd'] = pd.to_datetime(df['dateTimeEnd'], errors='coerce')
            
            # Видаляємо записи, де немає точної дати початку чи кінця
            df = df.dropna(subset=['dateTimeStart', 'dateTimeEnd'])
            
            # Рахуємо тривалість у хвилинах
            df['duration'] = (df['dateTimeEnd'] - df['dateTimeStart']).dt.total_seconds() / 60
            df['date'] = df['dateTimeStart'].dt.date
            
            return df
        else:
            st.error("У файлі не знайдені колонки 'dateTimeStart' та 'dateTimeEnd'. Перевірте структуру файлу.")
            return pd.DataFrame()
            
    except FileNotFoundError:
        st.error("Файл 'airAlert.json' не знайдено! Переконайтеся, що ви завантажили його на GitHub у правильну папку.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Сталася помилка під час обробки файлу тривог: {e}")
        return pd.DataFrame()

# ==========================================
# 2. АВТОРИЗАЦІЯ ТА ЧИТАННЯ EARTH DATA
# ==========================================
@st.cache_resource
def setup_nasa_auth():
    # Авторизація на порталі NASA Earthdata
    if "EARTHDATA_USERNAME" in st.secrets:
        os.environ["EARTHDATA_USERNAME"] = st.secrets["EARTHDATA_USERNAME"]
        os.environ["EARTHDATA_PASSWORD"] = st.secrets["EARTHDATA_PASSWORD"]
    try:
        earthaccess.login(strategy="environment")
        return True
    except Exception:
        st.warning("⚠️ Налаштуйте авторизацію Earthdata у Streamlit Secrets.")
        return False

def get_urls_for_period(start_date, end_date):
    try:
        with open("EARTH data.md", "r") as file:
            content = file.read()
        
        # Витягуємо всі лінки
        urls = re.findall(r'(https?://[^\s]+\.nc)', content)
        filtered_urls = []
        
        for url in urls:
            # Шукаємо дату в імені файлу (наприклад, 20240101)
            match = re.search(r'NO2____(\d{8})', url)
            if match:
                file_date = pd.to_datetime(match.group(1)).date()
                if isinstance(start_date, pd.Timestamp): start_date = start_date.date()
                if isinstance(end_date, pd.Timestamp): end_date = end_date.date()
                
                # Забираємо тільки ті файли, які входять у вибраний період
                if start_date <= file_date <= end_date:
                    filtered_urls.append(url)
        return filtered_urls
    except FileNotFoundError:
        st.error("Файл 'EARTH data.md' не знайдено у репозиторії!")
        return []

@st.cache_data
def process_earth_data_streaming(start_date, end_date):
    urls = get_urls_for_period(start_date, end_date)
    if not urls or not setup_nasa_auth():
        return pd.DataFrame()

    try:
        file_objects = earthaccess.open(urls)
    except Exception:
        return pd.DataFrame()

    daily_no2 = []
    # Обмежувальна коробка (Bounding Box) для Києва
    lat_min, lat_max = 50.2, 50.6
    lon_min, lon_max = 30.2, 30.8

    # Ліниве читання (потокове завантаження лише пікселів Києва)
    for idx, f_obj in enumerate(file_objects):
        try:
            with xr.open_dataset(f_obj, group='PRODUCT', engine='h5netcdf') as ds:
                mask = ((ds.latitude >= lat_min) & (ds.latitude <= lat_max) & 
                        (ds.longitude >= lon_min) & (ds.longitude <= lon_max))
                no2_kyiv = ds.nitrogendioxide_tropospheric_column.where(mask, drop=True)
                
                if no2_kyiv.size > 0:
                    avg_no2 = float(no2_kyiv.mean().values)
                    date_val = pd.to_datetime(ds.time.values[0]).date()
                    daily_no2.append({"date": date_val, "avg_no2_level": avg_no2})
        except Exception:
            continue

    if daily_no2:
        return pd.DataFrame(daily_no2).groupby('date').mean().reset_index()
    return pd.DataFrame()

# ==========================================
# 3. ВІЗУАЛІЗАЦІЯ ІНТЕРФЕЙСУ
# ==========================================
st.header("1. Аналіз тривог у Києві")
alarms_df = load_alarms_data()
top_duration = pd.DataFrame()

# Кнопка для конвертації та завантаження CSV
if not alarms_df.empty:
    st.success("Дані про тривоги успішно зчитано з `airAlert.json`!")
    csv = alarms_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Завантажити повну історію тривог як CSV",
        data=csv,
        file_name='air_alerts_history_kyiv.csv',
        mime='text/csv',
    )

if not alarms_df.empty and 'date' in alarms_df.columns:
    daily_alarms = alarms_df.groupby('date').agg(
        total_duration_min=pd.NamedAgg(column='duration', aggfunc='sum'),
        alarms_count=pd.NamedAgg(column='duration', aggfunc='count')
    ).reset_index()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Дні з найбільшою кількістю тривог")
        top_count = daily_alarms.sort_values(by='alarms_count', ascending=False).head(5)
        st.dataframe(top_count[['date', 'alarms_count']])

    with col2:
        st.subheader("Дні з найдовшими тривогами (сумарно)")
        top_duration = daily_alarms.sort_values(by='total_duration_min', ascending=False).head(5)
        
        # Округлюємо хвилини для красивого вигляду
        top_duration_display = top_duration.copy()
        top_duration_display['total_duration_min'] = top_duration_display['total_duration_min'].round(1)
        st.dataframe(top_duration_display[['date', 'total_duration_min']])

st.header("2. Співставлення забруднення повітря")
period_start = pd.to_datetime("2022-02-17 00:00").date()
period_end = pd.to_datetime("2022-02-24 03:00").date()

st.write(f"**Базовий період (Перед вторгненням):** {period_start} - {period_end}")
base_avg = None

with st.spinner("Завантаження даних NASA для базового періоду..."):
    base_pollution = process_earth_data_streaming(period_start, period_end)
    if not base_pollution.empty:
        base_avg = base_pollution['avg_no2_level'].mean()
        st.metric("Середній рівень забруднення", f"{base_avg:.6f} mol/m²")
    else:
        st.info("Немає супутникових знімків для базового періоду (лютий 2022) у файлі 'EARTH data.md'. Додайте посилання, щоб побачити результат.")

selected_week = st.date_input("Виберіть початок тижня для порівняння (під час вторгнення):", value=datetime(2024, 9, 1))
if selected_week:
    comp_end = selected_week + pd.Timedelta(days=7)
    st.write(f"**Період порівняння:** {selected_week} - {comp_end}")
    
    with st.spinner("Отримання даних NASA для вибраного тижня..."):
        comp_pollution = process_earth_data_streaming(selected_week, comp_end)
        
        if not comp_pollution.empty and base_avg is not None:
            comp_avg = comp_pollution['avg_no2_level'].mean()
            delta = comp_avg - base_avg
            st.metric("Рівень забруднення (Вибраний тиждень)", f"{comp_avg:.6f} mol/m²", delta=f"{delta:.6f} mol/m²", delta_color="inverse")
        elif not comp_pollution.empty:
            st.metric("Рівень забруднення (Вибраний тиждень)", f"{comp_pollution['avg_no2_level'].mean():.6f} mol/m²")
        else:
            st.info("Немає супутникових даних у файлі 'EARTH data.md' для вибраного тижня.")

# ==========================================
# 4. СПІВСТАВЛЕННЯ ТРИВОГ І ПОВІТРЯ
# ==========================================
if not top_duration.empty:
    st.header("3. Співставлення забруднення у дні найдовших тривог")
    
    comparison_data = []
    top_days = top_duration['date'].tolist()
    
    with st.spinner("Підтягуємо дані NASA для днів із тривогами (зачекайте, це може зайняти хвилину)..."):
        for day in top_days:
            day_pol = process_earth_data_streaming(day, day)
            avg_pol = day_pol['avg_no2_level'].mean() if not day_pol.empty else None
            
            alarms_info = top_duration[top_duration['date'] == day].iloc[0]
            comparison_data.append({
                "Дата": day,
                "Тривалість тривог (хв)": round(alarms_info['total_duration_min'], 1),
                "Середній рівень NO2": round(avg_pol, 6) if avg_pol else "Немає посилань у EARTH data.md"
            })
            
    st.table(pd.DataFrame(comparison_data))
