import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os


# =========================
# 設定區
# =========================

# 校內舊 API
URL = "https://ga50.fcu.edu.tw/iCasApi/Meter/SelectData"
# 共善樓 API
URL_VIRTUOSI = "http://172.18.5.109/WaWebService/JSON/GetDataLog/WebAccessEMS"
# 優先抓環境變數，抓不到就用校內實體 IP (或 localhost)
# URL_VIRTUOSI= os.getenv("VIRTUOSI_API_URL",  
#                         "http://172.18.5.109/WaWebService/JSON/GetDataLog/WebAccessEMS")
# URL_VIRTUOSI = os.getenv("VIRTUOSI_API_URL")

# # 判斷：如果你人在 Windows (本機)，且抓到的是 docker 的網址
# if os.name == 'nt' and (not URL_VIRTUOSI or "host.docker.internal" in URL_VIRTUOSI):
#     # 強制修正為實體 IP，不論 .env 寫了什麼
#     URL_VIRTUOSI = "http://172.18.5.109/WaWebService/JSON/GetDataLog/WebAccessEMS"

# print(f"共善樓目前使用的 URL 是: {URL_VIRTUOSI}")

# 共善樓透過 Basic Auth
BASIC_AUTH = ('admin', 'virtuosi')

# METER_ID = "009"  # 先抓單一表測試
# BASE_DATE_STR = "2026-01-22"  # 要抓的日期
# LOOKBACK_DAYS = 2  # 往前抓幾天
DELAY_SECONDS = 1.2  # 每次請求延遲，避免被伺服器封鎖

# 完整 header 從 POSTMAN 成功測試複製過來
HEADERS_CAMPUS = {
    'SystemKey': '5RsVJXEbVxslSdSZEhQRLip0tKoQRLURvXbP1KF35U0=',
    'User-Agent': 'PostmanRuntime/7.32.3',  # 模擬 POSTMAN
    'Accept': '*/*',
    'Connection': 'keep-alive'
}


# =========================
# 1️⃣ 原有的校內電表抓取邏輯 (單點抓取)
# =========================
def fetch_meter_data(date_str: str, meter_id: str, print_log):
    dt = datetime.strptime(f"{date_str} 00:00:00", "%Y-%m-%d %H:%M:%S")
    end_dt = dt + timedelta(days=1)

    # 使用 Session 重用 TCP 連線，避免 WinError 10048
    session = requests.Session()
    session.headers.update(HEADERS_CAMPUS)

    last_printed_minute = None  # 控制進度訊息輸出

    while dt < end_dt:
        params = {
            "MeterId": meter_id,
            "DataTimeStamp": dt.isoformat()
        }
        try:
            resp = session.get(URL, params=params, verify=False, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            if result.get("success") and result.get("data"):
                print_log(f"✅ {meter_id} {dt} 回傳結果：\n{result}")
                return result
        except requests.HTTPError as e:
            if e.response.status_code != 404:
                print_log(f"⚠️ {meter_id} {dt} HTTP error: {e}")
            else:
                print_log(f"⚠️ {meter_id} {dt} 無資料，繼續...")
        except Exception as e:
            print_log(f"❌ {dt} 連線失敗: {e}")

        dt += timedelta(minutes=1)
        time.sleep(DELAY_SECONDS)

    print_log(f"⚠️ {meter_id} {date_str} 整天都沒資料")
    return None


# =========================
# 2️⃣ 新的共善樓抓取邏輯 (批量趨勢抓取)
# =========================
def fetch_virtuosi_hall_data(start_date: str, records: int, print_log) -> pd.DataFrame:
    """
    共善樓專用：一次抓取多個電力參數並合併為 DataFrame
    start_date: yyyy-mm-dd
    records: 欲抓取的筆數 (例如 1 代表當天)
    """
    # 定義要對齊的點位清單
    points = [
        "PM_MVCB:KWH", "PM_MVCB:KW", "PM_MVCB:PF", "PM_MVCB:HZ",
        "PM_MVCB:V1", "PM_MVCB:V2", "PM_MVCB:V3",
        "PM_MVCB:I1", "PM_MVCB:I2", "PM_MVCB:I3", "PM_MVCB:KVAR"
    ]
    
    all_data = {}
    session = requests.Session()
    session.headers.update({
            'User-Agent': 'PostmanRuntime/7.32.3',
            'Accept': 'application/json'
        })

    print_log(f"🚀 開始抓取共善樓 (virtuosi_hall) 資料，起點：{start_date}，筆數：{records}")

    for point in points:
        params = {
            "StartTime": f"{start_date} 00:00:00",
            "IntervalType": "D", # 以日為單位
            "Interval": 1,
            "Records": records,
             "Tags":[{
                "Name": point,
                "DataType":"0" # Last 值
            }]
        }
        
        try:
            # 使用 POST 並將 params 改為 json 傳遞
            resp = session.post(
                URL_VIRTUOSI, 
                json=params,
                auth=BASIC_AUTH, 
                verify=False, 
                timeout=15
            )

            resp.raise_for_status()
            result = resp.json()
            
            if "DataLog" in result and len(result["DataLog"]) > 0:
                log = result["DataLog"][0]
                values = pd.to_numeric(log.get("Values", []), errors='coerce')
                # 建立以時間為索引的 Series
                times = pd.date_range(start=log["StartTime"], periods=len(values), freq='D')
                all_series = pd.Series(values, index=times)
                all_data[point] = all_series
                print_log(f"✅ 取得點位 {point} 成功")
            else:
                print_log(f"⚠️ 點位 {point} 無資料回傳")
                
        except Exception as e:
            print_log(f"❌ 抓取點位 {point} 失敗: {e}")
        
        time.sleep(0.5) # 共善樓 API 批次抓取，延遲可縮短

    if not all_data:
        return pd.DataFrame()

    # 合併所有點位資料
    df = pd.DataFrame(all_data)
    df.index.name = 'meter_data_timestamp'
    df = df.reset_index()

    # 3️⃣ 對齊資料庫欄位格式 (包含 NULL 處理)
    final_df = pd.DataFrame({
        "meter_id": "virtuosi_hall",
        "meter_data_timestamp": df['meter_data_timestamp'],
        "meter_voltage_r": df.get('PM_MVCB:V1'),
        "meter_voltage_s": df.get('PM_MVCB:V2'),
        "meter_voltage_t": df.get('PM_MVCB:V3'),
        "meter_current_r": df.get('PM_MVCB:I1'),
        "meter_current_s": df.get('PM_MVCB:I2'),
        "meter_current_t": df.get('PM_MVCB:I3'),
        "meter_active_power_kw": df.get('PM_MVCB:KW'),
        "meter_energy_kwh_total": df.get('PM_MVCB:KWH'),
        "meter_apparent_power_kva": None,      # NULL
        "meter_reactive_power_kvar": df.get('PM_MVCB:KVAR'),
        "meter_energy_kvarh_total": None,      # NULL
        "meter_frequency_hz": df.get('PM_MVCB:HZ'),
        "meter_power_factor": df.get('PM_MVCB:PF'),
        "meter_current_transform_ratio": None,      # NULL
        "meter_voltage_transform_ratio": None       # NULL
    })

    return final_df    


# if __name__ == "__main__":
#     # 先轉成 datetime
#     base_date = datetime.strptime(BASE_DATE_STR, "%Y-%m-%d")
#     for i in range(LOOKBACK_DAYS):
#         date_to_fetch = (base_date - timedelta(days=i)).strftime("%Y-%m-%d")
#         fetch_meter_data(date_to_fetch, METER_ID)

