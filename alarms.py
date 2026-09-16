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
        
        # Спробуємо знайти колонки початку та кінця (можуть називатися start/end, started_at/finished_at тощо)
        start_col = next((col for col in df.columns if 'start' in col.lower() or 'begin' in col.lower()), None)
        end_col = next((col for col in df.columns if 'end' in col.lower() or 'finish' in col.lower()), None)
        
        if start_col and end_col:
            df[start_col] = pd.to_datetime(df[start_col], errors='coerce')
            df[end_col] = pd.to_datetime(df[end_col], errors='coerce')
            df['duration'] = (df[end_col] - df[start_col]).dt.total_seconds() / 60
            df['date'] = df[start_col].dt.date
        else:
            # Якщо колонки не знайшлися автоматично, показуємо їх на екрані для дебагу
            st.error(f"Не вдалося знайти колонки початку/кінця. Доступні колонки в API: {list(df.columns)}")
            df['date'] = pd.NaT # Запобігаємо KeyError
            df['duration'] = 0
            
        return df
    except Exception as e:
        st.error(f"Помилка завантаження даних про тривоги: {e}")
        return pd.DataFrame()
