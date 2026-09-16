# ==========================================
# 1. ЗАВАНТАЖЕННЯ ДАНИХ ПРО ТРИВОГИ
# ==========================================
@st.cache_data
def load_alarms_data():
    resource_id = "e1216fe6-7cbd-41ad-b478-85983a2e2669"
    url = f"https://data.kyivcity.gov.ua/api/action/datastore_search?resource_id={resource_id}&limit=10"
    
    # Додаємо "маскування" під звичайний браузер, щоб уникнути помилки 403 Forbidden
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
        
        if 'resource_url' in df_meta.columns:
            actual_file_url = df_meta['resource_url'].iloc[0]
            # Також передаємо маскування при завантаженні самої таблиці
            response_csv = requests.get(actual_file_url, headers=headers)
            response_csv.raise_for_status()
            
            from io import StringIO
            df = pd.read_csv(StringIO(response_csv.text))
        else:
            df = df_meta
        
        start_col = next((col for col in df.columns if any(x in col.lower() for x in ['start', 'begin', 'from', 'початок'])), None)
        end_col = next((col for col in df.columns if any(x in col.lower() for x in ['end', 'finish', 'to', 'кінець'])), None)
        
        if start_col and end_col:
            df[start_col] = pd.to_datetime(df[start_col], errors='coerce')
            df[end_col] = pd.to_datetime(df[end_col], errors='coerce')
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
