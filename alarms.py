import streamlit as st
import pandas as pd
import requests
import xarray as xr
import earthaccess
import re
import os
from datetime import datetime

# Налаштування сторінки
st.set_page_config(page_title="Аналіз якості повітря та тривог у Києві", layout="wide")
st.title("Аналіз ділянок Києва: Забруднення повітря та Повітряні тривоги")

# ==========================================
# 1. ЗАВАНТАЖЕННЯ ДАНИХ ПРО ТРИВОГИ
# ==========================================
@st.cache_data
def load_alarms_data():
    resource_id = "e1216fe6-7cbd-41ad-b478-85983a2e2669"
    url = f"https://data.kyivcity.gov.ua/api/action/datastore_search?resource_id={resource_id}&limit=10"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        records = response.json().get("result", {}).get("records", [])
        
        if not records:
            return pd.DataFrame()
            
        df_meta = pd.DataFrame(records)
        
        # Якщо API повернуло посилання на файл (resource_url), читаємо його
        if 'resource_url' in df_meta.columns:
            actual_file_url = df_meta['resource_url'].iloc[0]
            df = pd.read_csv(actual_file_url)
        else:
            df = df_meta
        
        # Шукаємо колонки з датами у завантаженому файлі
        start_col = next((col for col in df.columns if any(x in col.lower() for x in ['start', 'begin', 'from', 'початок'])), None)
        end_col = next((col for col in df.columns if any(x in col.lower() for x in ['end', 'finish', 'to', 'кінець'])), None)
        
        if start_col and end_col:
            df[start_col] = pd.to_datetime(df[start_col], errors='coerce')
            df[end_col] = pd.to_datetime(df[end_col], errors='coerce')
            
            # Видаляємо биті записи
            df = df.dropna(subset=[start_col, end_col])
            
            df['duration'] = (df[end_col] - df[start_col]).dt.total_seconds() / 60
            df['date'] = df[start_col].dt.date
        else:
            st.error(f"Файл завантажено, але не вдалося розпізнати колонки дат. Колонки у файлі: {list(df.columns)}")
            df['date'] = pd.NaT
            df['duration'] = 0
            
        return df
    except Exception as e:
        st.error(f"Помилка завантаження даних про тривоги: {e}")
        return pd.DataFrame()

# ==========================================
# 2. АВТОРИЗАЦІЯ ТА ЧИТАННЯ EARTH DATA
# ==========================================
@st.cache_resource
def setup_nasa_auth():
    # Підтягуємо секрети з Streamlit Cloud
    if "EARTHDATA_USERNAME" in st.secrets:
        os.environ["EARTHDATA_USERNAME"] = st.secrets["EARTHDATA_USERNAME"]
        os.environ["EARTHDATA_PASSWORD"] = st.secrets["EARTHDATA_PASSWORD"]
    
    try:
        earthaccess.login(strategy="environment")
        return True
    except Exception:
        st.warning("⚠️ Налаштуйте авторизацію Earthdata у Streamlit Secrets (EARTHDATA_USERNAME та EARTHDATA_PASSWORD).")
        return False

def get_urls_for_period(start_date, end_date):
    try:
        with open("EARTH data.md", "r") as file:
            content = file.read()
            
        urls = re.findall(r'(https?://[^\s]+\.nc)', content)
        filtered_urls = []
        for url in urls:
            match = re.search(r'NO2____(\d{8})', url)
            if match:
                file_date = pd.to_datetime(match.group(1)).date()
                
                # Конвертація на випадок, якщо дати прийшли у форматі Timestamp
                if isinstance(start_date, pd.Timestamp): start_date = start_date.date()
                if isinstance(end_date, pd.Timestamp): end_date = end_date.date()
                
                if start_date <= file_date <= end_date:
                    filtered_urls.append(url)
        return filtered_urls
    except FileNotFoundError:
        st.error("Файл 'EARTH data.md' не знайдено у репозиторії!")
        return []

@st.cache_data
def process_earth_data_streaming(start_date, end_date):
    urls = get_urls_for_period(start_date, end_date)
    if not urls:
        return pd.DataFrame()
        
    if not setup_nasa_auth():
        return pd.DataFrame()

    try:
        file_objects = earthaccess.open(urls)
    except Exception as e:
        st.error(f"Помилка доступу до NASA: {e}")
        return pd.DataFrame()

    daily_no2 = []
    # Координати Києва
    lat_min, lat_max = 50.2, 50.6
    lon_min, lon_max = 30.2, 30.8

    for idx, f_obj in enumerate(file_objects):
        try:
            with xr.open_dataset(f_obj, group='PRODUCT', engine='h5netcdf') as ds:
                mask = (
                    (ds.latitude >= lat_min) & (ds.latitude <= lat_max) &
                    (ds.longitude >= lon_min) & (ds.longitude <= lon_max)
                )
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

if not alarms_df.empty and 'date' in alarms_df.columns and not alarms_df['date'].isna().all():
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
        st.subheader("Дні з найдовшими тривогами")
        top_duration = daily_alarms.sort_values(by='total_duration_min', ascending=False).head(5)
        st.dataframe(top_duration[['date', 'total_duration_min']])
else:
    st.warning("Дані про тривоги наразі недоступні або мають невідому структуру.")

st.header("2. Співставлення забруднення повітря")
period_start = pd.to_datetime("2022-02-17 00:00").date()
period_end = pd.to_datetime("2022-02-24 03:00").date()

st.write(f"**Базовий період (Перед вторгненням):** {period_start} - {period_end}")
base_avg = None

with st.spinner("Завантаження даних NASA для базового періоду (це може зайняти хвилину)..."):
    base_pollution = process_earth_data_streaming(period_start, period_end)
    if not base_pollution.empty:
        base_avg = base_pollution['avg_no2_level'].mean()
        st.metric("Середній рівень забруднення", f"{base_avg:.6f} mol/m²")
    else:
        st.info("Немає супутникових знімків для базового періоду (лютий 2022) у вашому файлі 'EARTH data.md'. Додайте посилання за ці дати, щоб побачити результат.")

selected_week = st.date_input("Виберіть початок тижня для порівняння (під час вторгнення):", value=datetime(2024, 9, 1))
if selected_week:
    comp_end = selected_week + pd.Timedelta(days=7)
    st.write(f"**Період порівняння:** {selected_week} - {comp_end}")
    
    with st.spinner("Отримання даних NASA для вибраного тижня..."):
        comp_pollution = process_earth_data_streaming(selected_week, comp_end)
        if not comp_pollution.empty and base_avg is not None:
            comp_avg = comp_pollution['avg_no2_level'].mean()
            delta = comp_avg - base_avg
            st.metric("Середній рівень забруднення (Вибраний тиждень)", f"{comp_avg:.6f} mol/m²", delta=f"{delta:.6f} mol/m²", delta_color="inverse")
        elif not comp_pollution.empty and base_avg is None:
            comp_avg = comp_pollution['avg_no2_level'].mean()
            st.metric("Середній рівень забруднення (Вибраний тиждень)", f"{comp_avg:.6f} mol/m²")
        elif comp_pollution.empty:
            st.info("Немає супутникових даних у файлі 'EARTH data.md' для вибраного тижня.")

# ==========================================
# 4. СПІВСТАВЛЕННЯ ТРИВОГ І ПОВІТРЯ
# ==========================================
if not top_duration.empty:
    st.header("3. Співставлення забруднення у дні найдовших тривог")
    st.write("Перевірка рівня NO2 у Києві в дні з найтривалішими тривогами (топ-5).")
    
    comparison_data = []
    top_days = top_duration['date'].tolist()
    
    with st.spinner("Підтягуємо дані NASA для днів із тривогами..."):
        for day in top_days:
            day_pol = process_earth_data_streaming(day, day)
            avg_pol = day_pol['avg_no2_level'].mean() if not day_pol.empty else None
            
            alarms_info = top_duration[top_duration['date'] == day].iloc[0]
            comparison_data.append({
                "Дата": day,
                "Тривалість тривог (хв)": round(alarms_info['total_duration_min'], 1),
                "Середній рівень NO2": round(avg_pol, 6) if avg_pol else "Немає даних у EARTH data.md"
            })
            
    st.table(pd.DataFrame(comparison_data))
