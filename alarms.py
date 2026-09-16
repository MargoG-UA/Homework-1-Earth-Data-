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
    url = f"https://data.kyivcity.gov.ua/api/action/datastore_search?resource_id={resource_id}&limit=10000"
    
    # Маскування під звичайний браузер для обходу помилки 403 Forbidden
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        records = response.json().get("result", {}).get("records", [])
        
        if not records:
            return pd.DataFrame()
            
        df_meta = pd.DataFrame(records)
        
        # Якщо API повернуло посилання на файл (resource_url), читаємо його
        if 'resource_url' in df_meta.columns:
            actual_file_url = df_meta['resource_url'].iloc[0]
            response_csv = requests.get(actual_file_url, headers=headers)
            response_csv.raise_for_status()
            from io import StringIO
            df = pd.read_csv(StringIO(response_csv.text))
        else:
            df = df_meta
        
        # Шукаємо колонки з датами у завантаженому файлі
        start_col = next((col for col in df.columns if any(x in col.lower() for x in ['start', 'begin', 'from', 'початок'])), None)
        end_col = next((col for col in df.columns if any(x in col.lower() for x in ['end', 'finish', 'to', 'кінець'])), None)
        
        if start_col and end_col:
            df[start_col] = pd.to_datetime(df[start_col], errors='coerce')
            df[end_col] = pd.to_datetime(df[end_col], errors='coerce')
            df = df.dropna(subset=[start_col, end_col])
            df['duration'] = (df[end_col] - df[start_col]).dt.total_seconds() / 60
            df['date'] = df[start_col].dt.date
        else:
            st.error(f"Файл завантажено, але не вдалося розпізнати колонки дат. Колонки: {list(df.columns)}")
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
    if "EARTHDATA_USERNAME" in st.secrets:
        os.environ["EARTHDATA_USERNAME"] = st.secrets["EARTHDATA_USERNAME"]
        os.environ["EARTHDATA_PASSWORD"] = st.secrets["EARTHDATA_PASSWORD"]
    
    try:
        earthaccess.login(strategy="environment")
        return True
    except Exception:
        st.warning("⚠️ Налаштуйте авторизацію Earthdata у Streamlit### Diagnosing the Error in image_f32d9a.png

Based on the traceback provided in **image_f32d9a.png**, your Streamlit application is crashing due to a `NameError` on line 4 of your `alarms.py` file. 

---

### What is happening?

The Python interpreter is flagging the line `@st.cache_data` because it does not recognize the module name **`st`**. A `NameError` occurs when you try to use a variable, function, or module that hasn't been defined or imported into your current namespace.

### How to fix it

This almost always happens when you forget to import the Streamlit library at the beginning of your script. To fix this, you need to import Streamlit and alias it as `st` before attempting to use any of its decorators or functions.

Add the following line to the very top of your `alarms.py` file:

```python
import streamlit as st
