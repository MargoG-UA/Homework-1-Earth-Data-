import streamlit as st
import pandas as pd
import requests
import xarray as xr
import earthaccess
import re
import os
from datetime import datetime

st.set_page_config(page_title="Аналіз якості повітря та тривог у Києві", layout="wide")

st.title("Аналіз ділянок Києва: Забруднення повітря та Повітряні тривоги")

# ==========================================
# 1. ЗАВАНТАЖЕННЯ ДАНИХ ПРО ТРИВОГИ
# ==========================================
@st.cache_data
def load_alarms_data():
    resource_id = "e1216fe6-7cbd-41ad-b478-85983a2e2669"
    url = f"https://data.kyivcity.gov.ua/api/action/datastore_search?resource_id={resource_id}&limit=10000"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        records = response.json().get("result", {}).get("records", [])
        
        if not records:
            return pd.DataFrame()
            
        df = pd.DataFrame(records)
        if 'start_time' in df.columns and 'end_time' in df.columns:
            df['start_time'] = pd.to_datetime(df['start_time'])
            df['end_time'] = pd.to_datetime(df['end_time'])
            df['duration'] = (df['end_time'] - df['start_time']).dt.total_seconds() / 60
            df['date'] = df['start_time'].dt.date
        return df
    except Exception as e:
        st.error(f"Помилка завантаження даних про тривоги: {e}")
        return pd.DataFrame()

# ==========================================
# 2. АВТОРИЗАЦІЯ ТА ЧИТАННЯ EARTH DATA
# ==========================================
@st.cache_resource
def setup_nasa_auth():
    # Підтягуємо секрети з налаштувань Streamlit Cloud
    if "EARTHDATA_USERNAME" in st.secrets:
        os.environ["EARTHDATA_USERNAME"] = st.secrets["EARTHDATA_USERNAME"]
        os.environ["EARTHDATA_PASSWORD"] = st.secrets["EARTHDATA_PASSWORD"]
    
    try:
        earthaccess.login(strategy="environment")
        return True
    except Exception as e:
        st.warning("Будь ласка, налаштуйте авторизацію Earthdata у Streamlit Secrets.")
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
                if start_date <= file_date <= end_date:
                    filtered_urls.append(url)
        return filtered_urls
    except FileNotFoundError:
        st.error("Файл 'EARTH data.md' не знайдено!")
        return []

@st.cache_data
def process_earth_data_streaming(start_date, end_date):
    urls = get_urls_for_period(start_date, end_date)
    if not urls:
        return pd.DataFrame()
        
    if not setup_nasa_auth():
        return pd.DataFrame()

    file_objects = earthaccess.open(urls)
    daily_no2 = []
    
    lat_min, lat_max = 50.3, 50.6
    lon_min, lon_max = 30.3, 30.7

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
# ІНТЕРФЕЙС
# ==========================================
st.header("1. Аналіз тривог у Києві")
alarms_df = load_alarms_data()

top_duration = pd.DataFrame()
if not alarms_df.empty:
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
    st.warning("Дані про тривоги наразі недоступні.")

st.header("2. Співставлення забруднення повітря")
period_start = pd.to_datetime("2022-02-17 00:00").date()
period_end = pd.to_datetime("2022-02-24 03:00").date()

st.write(f"**Базовий період (Перед вторгненням):** {period_start} - {period_end}")
with st.spinner("Завантаження даних NASA (ліниве читання)..."):
    base_pollution = process_earth_data_streaming(period_start, period_end)
    if not base_pollution.empty:
        base_avg = base_pollution['avg_no2_level'].mean()
        st.metric("Середній рівень забруднення", f"{base_avg:.6f} mol/m²")
    else:
        st.info("Немає супутникових знімків для базового періоду у 'EARTH data.md'.")
        base_avg = None

selected_week = st.date_input("Виберіть початок тижня для порівняння:", value=datetime(2024, 9, 1))
if selected_week:
    comp_end = selected_week + pd.Timedelta(days=7)
    st.write(f"**Період порівняння:** {selected_week} - {comp_end}")
    
    with st.spinner("Завантаження даних NASA..."):
        comp_pollution = process_earth_data_streaming(selected_week, comp_end)
        if not comp_pollution.empty and base_avg:
            comp_avg = comp_pollution['avg_no2_level'].mean()
            delta = comp_avg - base_avg
            st.metric("Середній рівень забруднення (Вибраний тиждень)", f"{comp_avg:.6f} mol/m²", delta=f"{delta:.6f} mol/m²", delta_color="inverse")
