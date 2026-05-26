import requests
from urllib3.exceptions import InsecureRequestWarning
import warnings

# =========================
# 關閉 InsecureRequestWarning
# =========================
warnings.simplefilter('ignore', InsecureRequestWarning)

# =========================
# 設定區
# =========================
BASE_URL = "https://ga50.fcu.edu.tw/iCasApi/Meter/Select"
HEADERS = {
    'SystemKey': '5RsVJXEbVxslSdSZEhQRLip0tKoQRLURvXbP1KF35U0=',
    'User-Agent': 'PostmanRuntime/7.32.3',   # 模擬 POSTMAN
    'Accept': '*/*',
    'Connection': 'keep-alive'
}

# =========================
# 抓取 API 清單
# =========================
def fetch_meter_list(print_log):
    try:
        resp = requests.get(BASE_URL, headers=HEADERS, verify=False, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("success") and data.get("data"):
            print_log(f"✅ API 回傳 {len(data['data'])} 筆電表清單")
            for meter in data["data"]:
                print_log(f"DeviceID: {meter.get('DeviceID')}, MeterName: {meter.get('MeterName')}")
            return data["data"]
        else:
            print_log("⚠️ API 回傳成功，但沒有資料")
            return []
    except requests.HTTPError as e:
        print_log(f"⚠️ HTTP error: {e}")
    except Exception as e:
        print_log(f"❌ 連線失敗: {e}")
    return []

# =========================
# 主程式
# =========================
if __name__ == "__main__":
    fetch_meter_list()
