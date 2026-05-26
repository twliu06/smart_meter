import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from utils.diff_etl import run_diff_etl
from utils.logger import get_logger
from utils.meter_utils import get_last_date
from marts.sensor_campus_meter_daily.fetch_data import fetch_daily_usage
import warnings
from urllib3.exceptions import InsecureRequestWarning

# 關閉 InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)

BASE_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(BASE_DIR, "logs")

print_log = get_logger(
    log_dir=LOG_DIR,
    log_prefix="stg_campus_meter_daily"
)

TABLE_NAME = "public.sensor_campus_meter_daily"
KEY_COLS = ["meter_id", "usage_date"]
COMPARE_COLS = ["meter_daily_energy_kwh", "meter_daily_energy_kvarh"]

def run_stg_logic(target_id, default_start):
    """
    通用的 STG 計算邏輯
    target_id: 'campus' (代表舊有的群組) 或是 'virtuosi_hall'
    default_start: 該建築物的初始日期
    """
    last_stg_date = get_last_date(TABLE_NAME, db_type="stg", date_col="usage_date", meter_id=target_id)

    # 2. 💡 新增：取得 RAW 最後存檔日 (關鍵！)
    last_raw_date = get_last_date("sensor.campus_meter_daily", db_type="raw", meter_id=target_id)
    
    # 3. 計算起點
    start_date = pd.to_datetime(last_stg_date).normalize() + timedelta(days=1) if last_stg_date else pd.to_datetime(default_start)

    display_name = "共善樓電表" if target_id else "校內電表"
    # 4. 💡 修正判斷：如果 [STG最後一天] 已經等於 [RAW最後一天 - 1]，就代表沒戲唱了
    if last_raw_date:
        calculable_until = pd.to_datetime(last_raw_date).normalize() - timedelta(days=1)
        if start_date > calculable_until:
            print_log(f"ℹ️ {display_name}資料已達計算極限 (需等明日 Raw 入庫才能算 {start_date.date()})")
            return

    start_str = start_date.strftime("%Y-%m-%d")
    print_log(f"🚀 {display_name} 啟動 STG 計算：從 {start_str} 開始追趕...")

    # 2️⃣ 呼叫計算模組 (fetch_daily_usage 內部應支援帶入 meter_id 過濾)
    df_result = fetch_daily_usage(start_str, print_log, meter_id=target_id)

    if df_result is None or df_result.empty:
        print_log(f"⚠️ {display_name} 尚無足夠 Raw 資料可計算新區間。")
        return

    # 3️⃣ 寫入 STG (使用 diff_etl 確保不重複)
    run_diff_etl(df_result, TABLE_NAME, KEY_COLS, COMPARE_COLS, print_log, db_type="stg")
    
    processed_dates = sorted(df_result['usage_date'].unique())
    print_log(f"🎉 {display_name} 同步完成！範圍：{processed_dates[0]} ~ {processed_dates[-1]}")

def main(targets):
    # 根據輸入決定跑哪邊
    if "all" in targets or "campus" in targets:
        run_stg_logic(target_id=None, default_start="2025-09-01")
        
    if "all" in targets or "virtuosi_hall" in targets:
        # 共善樓
        run_stg_logic(target_id="virtuosi_hall", default_start="2025-09-01")

if __name__ == "__main__":
    args = [a.lower() for a in sys.argv[1:]]
    
    if len(args) > 0:
        main(args)
    else:
        print("\n❌ 缺少參數！")
        print("用法範例:")
        print("  python -m marts.meter_campus_meter_daily.main campus")
        print("  python -m marts.meter_campus_meter_daily.main virtuosi_hall")
        print("  python -m marts.meter_campus_meter_daily.main all")