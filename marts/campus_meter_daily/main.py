import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from utils.diff_etl import run_diff_etl
from utils.logger import get_logger
from utils.meter_utils import get_last_date, get_meter_ids, SKIP_METERS
from marts.campus_meter_daily.fetch_data import fetch_meter_data, fetch_virtuosi_hall_data
import warnings
from urllib3.exceptions import InsecureRequestWarning

# 關閉 InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)

BASE_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(BASE_DIR, "logs")

print_log = get_logger(
    log_dir=LOG_DIR,
    log_prefix="raw_campus_meter_daily"
)

TABLE_NAME = "sensor.campus_meter_daily"
KEY_COLS = ["meter_id", "meter_data_timestamp"]
# 這是對應 DB 的欄位清單
COMPARE_COLS = [
    "meter_voltage_r", "meter_voltage_s", "meter_voltage_t",
    "meter_current_r", "meter_current_s", "meter_current_t",
    "meter_active_power_kw", "meter_energy_kwh_total",
    "meter_apparent_power_kva", "meter_reactive_power_kvar",
    "meter_energy_kvarh_total", "meter_frequency_hz",
    "meter_power_factor", "meter_current_transform_ratio",
    "meter_voltage_transform_ratio"
]

def run_campus_logic():
    """ 1️⃣ 原有的校內電表邏輯：逐天、逐個 MeterID 抓取 """
    last_date = get_last_date(TABLE_NAME, db_type="raw", date_col="meter_data_timestamp", meter_id=None)
    start_date = pd.to_datetime(last_date) + timedelta(days=1) if last_date else datetime.strptime("2025-09-01", "%Y-%m-%d")
    
    # 校內邏輯通常一次抓一天
    today = pd.Timestamp.today().normalize()
    # 因共善樓只能抓到前一天的，所以統一把昨天的資料當成最新的
    if start_date >= today:
        print_log(f"ℹ️ 校內電表資料已是最新 (最後存檔日: {last_date if last_date else '無'})")
        return

    date_to_fetch = start_date.strftime("%Y-%m-%d")
    meter_ids = get_meter_ids()
    
    for meter_id in meter_ids:
        if meter_id in SKIP_METERS:
            continue
            
        data = fetch_meter_data(date_to_fetch, meter_id, print_log)
        if not data or not data.get("data"):
            continue

        df = pd.DataFrame([{
            "meter_id": d["MeterID"],
            "meter_data_timestamp": pd.to_datetime(d["DataTimeStamp"]).floor("s"),
            "meter_voltage_r": d["Vrs"],
            "meter_voltage_s": d["Vst"],
            "meter_voltage_t": d["Vtr"],
            "meter_current_r": d["IrCurrent"],
            "meter_current_s": d["IsCurrent"],
            "meter_current_t": d["ItCurrent"],
            "meter_active_power_kw": d["kW"],
            "meter_energy_kwh_total": d["kWH"],
            "meter_apparent_power_kva": d["kVA"],
            "meter_reactive_power_kvar": d["kVar"],
            "meter_energy_kvarh_total": d["kVarH"],
            "meter_frequency_hz": d["Hz"],
            "meter_power_factor": d["PF"],
            "meter_current_transform_ratio": d["CT"],
            "meter_voltage_transform_ratio": d["PT"]
        } for d in data["data"]])

        run_diff_etl(df, TABLE_NAME, KEY_COLS, COMPARE_COLS, print_log, db_type="raw")
        print_log(f"🎉 校內電表 {meter_id} {date_to_fetch} 同步完成")

def run_virtuosi_logic():
    """ 2️⃣ 共善樓邏輯：批量歷史抓取 """
    # 明確指定要找 virtuosi_hall 的最後日期
    last_date = get_last_date(TABLE_NAME, db_type="raw", meter_id="virtuosi_hall")
    
    start_date = last_date + timedelta(days=1) if last_date else datetime.strptime("2025-09-01", "%Y-%m-%d")    

    # 計算需要抓幾天 (records)
    today = pd.Timestamp.today().normalize()
    start_date = pd.to_datetime(start_date).normalize()
    delta_days = (today - start_date).days
    
    if delta_days <= 0:
        print_log(f"ℹ️ 共善樓電表資料已是最新 (最後存檔日: {last_date if last_date else '無'})")
        return

    df = fetch_virtuosi_hall_data(start_date.strftime("%Y-%m-%d"), delta_days, print_log)
    
    if df is not None and not df.empty:
        # 注意：fetch_virtuosi_hall_data 回傳時要把 TR 倍率、kva、kvarh 設為 None
        run_diff_etl(df, TABLE_NAME, KEY_COLS, COMPARE_COLS, print_log, db_type="raw")
        print_log(f"🎉 共善樓 (virtuosi_hall) 補檔完成: {start_date} ~ {start_date + pd.Timedelta(days=delta_days-1)}")

def main(targets):
    """
    targets: 傳入的參數列表，例如 ['campus', 'virtuosi_hall'] 或 ['all']
    """
    if "all" in targets:
        run_campus_logic()
        run_virtuosi_logic()
    else:
        if "campus" in targets:
            run_campus_logic()
        if "virtuosi_hall" in targets:
            run_virtuosi_logic()

if __name__ == "__main__":
    args = [a.lower() for a in sys.argv[1:]]
    
    if len(args) > 0:
        main(args)
    else:
        print("\n❌ 缺少參數！")
        print("用法範例:")
        print("  1️⃣ 跑校內電表: python -m marts.campus_meter_daily.main campus")
        print("  2️⃣ 跑共善樓:   python -m marts.campus_meter_daily.main virtuosi_hall")
        print("  3️⃣ 跑全部大樓: python -m marts.campus_meter_daily.main all")
        print("-" * 30)