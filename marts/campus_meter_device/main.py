import os
import pandas as pd
from marts.campus_meter_device.fetch_data import fetch_meter_list
from utils.diff_etl import run_diff_etl
from utils.logger import get_logger


BASE_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(BASE_DIR, "logs")

print_log = get_logger(
    log_dir=LOG_DIR,
    log_prefix="raw_campus_meter_device"
)

TABLE_NAME = "sensor.campus_meter_device"
KEY_COLS = ["device_id"]
COMPARE_COLS = ["meter_name"]

def main():
    # 1️⃣ 先抓 Device 清單
    devices = fetch_meter_list(print_log)
    if not devices:
        print_log("❌ 沒抓到任何 Device")
        return
    
    # 2️⃣ 轉成 DataFrame
    df = pd.DataFrame([{
        "device_id": d.get("DeviceID"),
        "meter_name": d.get("MeterName")
    } for d in devices])

    # 3️⃣ Diff-based ETL 寫入 DB
    run_diff_etl(df, TABLE_NAME, KEY_COLS, COMPARE_COLS, print_log)

    print_log("🎉 校內智慧電表清單同步完成")

if __name__ == "__main__":
    main()
