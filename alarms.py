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
    
    return df_alerts,
