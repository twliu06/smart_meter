import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from utils.db_raw import get_engine

def fetch_daily_usage(start_calc_date: str, print_log, meter_id: str = None) -> pd.DataFrame:
    """
    meter_id: 新增參數，若指定則只計算該電表，若為 None 則計算全表
    """
    engine = get_engine()
    calc_dt = datetime.strptime(start_calc_date, "%Y-%m-%d")
    base_date = (calc_dt - timedelta(days=1)).date()

    # 1️⃣ 增加 meter_id 過濾條件
    sql = """
        SELECT
            meter_id,
            meter_data_timestamp::date as usage_date,
            MAX(meter_energy_kwh_total) as kwh_total,
            MAX(meter_energy_kvarh_total) as kvarh_total
        FROM sensor.campus_meter_daily
        WHERE meter_data_timestamp::date >= %(base_date)s
    """
    params = {"base_date": base_date}
    
    if meter_id:
        sql += " AND meter_id = %(meter_id)s"
        params["meter_id"] = meter_id
        
    sql += " GROUP BY meter_id, meter_data_timestamp::date"

    df_raw = pd.read_sql(sql, engine, params=params)

    if df_raw.empty:
        print_log(f"⚠️ {meter_id if meter_id else '全表'} 自 {base_date} 起無任何 raw 資料")
        return pd.DataFrame()

    all_meter_results = []

    for m_id, group in df_raw.groupby("meter_id"):
        group['usage_date'] = pd.to_datetime(group['usage_date'])
        
        actual_min = group['usage_date'].min()
        actual_max = group['usage_date'].max()
        full_range = pd.date_range(start=actual_min, end=actual_max, freq='D')
        
        group = group.set_index('usage_date').reindex(full_range)
        
        # 💡 檢查 KWH：如果有值才插值
        if group['kwh_total'].notnull().any():
            group['kwh_total'] = group['kwh_total'].interpolate(method='linear', limit_area='inside')
            group['meter_daily_energy_kwh'] = group['kwh_total'].shift(-1) - group['kwh_total']
        else:
            group['meter_daily_energy_kwh'] = np.nan

        # 💡 檢查 KVARH：針對共善樓這種全 NULL 的情況，skip 插值避免噴錯
        if group['kvarh_total'].notnull().any():
            group['kvarh_total'] = group['kvarh_total'].interpolate(method='linear', limit_area='inside')
            group['meter_daily_energy_kvarh'] = group['kvarh_total'].shift(-1) - group['kvarh_total']
        else:
            # 共善樓會走這裡，直接給 NaN (NULL)
            group['meter_daily_energy_kvarh'] = np.nan
        
        group['meter_id'] = m_id
        all_meter_results.append(group.reset_index().rename(columns={'index': 'usage_date'}))

    # ... (後續合併邏輯不變) ...
    final_df = pd.concat(all_meter_results)
    final_df = final_df[final_df['usage_date'] >= pd.to_datetime(start_calc_date)]
    
    # 這裡只根據 kwh 判斷，因為 kvarh 可能是全空
    final_df = final_df.dropna(subset=['meter_daily_energy_kwh'])

    # 四捨五入 (加入 error='ignore' 防止因為全 NULL 導致 round 失敗)
    for col in ['meter_daily_energy_kwh', 'meter_daily_energy_kvarh']:
        final_df[col] = pd.to_numeric(final_df[col], errors='coerce').round(2)

    result = final_df[['meter_id', 'usage_date', 'meter_daily_energy_kwh', 'meter_daily_energy_kvarh']].copy()
    result['usage_date'] = result['usage_date'].dt.date

    print_log(f"✅ 計算完成，共產出 {len(result)} 筆資料")
    return result