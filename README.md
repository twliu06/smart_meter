# 校內智慧電表數據處理系統 (Smart Meter Data System)

這套系統負責自動化採集、清洗、計算並儲存校內各建築物的電力監控數據，包含校內舊有電力監控系統與共善樓（WebAccess/EMS）來源。

## 📂 核心模組說明

本系統由以下三個核心程式模組組成，負責從數據採集到應用層的完整 ETL 流程：

### 1. `campus_meter_daily` (每日原始資料表 - Raw Layer)
* **功能**：負責從各設備 API 抓取原始累積電量數據。
* **特性**：
    * **多來源整合**：支援校內傳統電力 API (使用 SystemKey) 與共善樓 API (使用 Basic Auth)。
    * **自動補洞**：根據資料庫 `MAX(meter_data_timestamp)` 自動計算起點，追趕最新進度。
    * **日累積快照**：抓取每日 00:00:00 的 `meter_energy_kwh_total` 等關鍵指標。
* **資料庫位置**：`sensor.campus_meter_daily`

### 2. `campus_meter_device` (設備清單 - Dimension Layer)
* **功能**：管理所有校內電表設備的元數據（Metadata）。
* **關鍵欄位**：`device_id`, `meter_name` 等。
* **用途**：作為數據關聯的核心，提供給彙整層進行資料標記與分類。

### 3. sensor_campus_meter_daily` (每日彙整資料表 - STG/App Layer)
* **功能**：將原始的「累積值」轉換為具備分析價值的「用量值」。
* **計算指標**：
    * **每日用電量 (kwh)**：透過 `(今日累積值 - 昨日累積值)` 計算差額。
    * **功率分析**：彙整每日平均功率、最高需量、功率因數等。
* **數據優化**：
    * **線性插值**：若 Raw 資料有缺失，自動採用線性平分差額，確保電力趨勢不中斷。
    * **異動寫入 (Diff ETL)**：僅針對有變動或新增的日期進行更新，節省 I/O 成本。
* **資料庫位置**：`public.sensor_campus_meter_daily`

---

## 🛠 技術架構

* **開發語言**：Python 3.x
* **數據處理**：Pandas, NumPy
* **資料庫**：PostgreSQL / MySQL (支援 SQLAlchemy 引擎)
* **認證機制**：SystemKey Header / HTTP Basic Authentication

---

## 🚀 執行與操作

### 環境準備
```bash
# 安裝必要套件
pip install pandas requests sqlalchemy psycopg2-binary
```

### 執行數據採集 (Raw)
```bash
# 抓取校內傳統電表進度
python -m marts.campus_meter_daily.main campus

# 抓取共善樓電表進度
python -m marts.campus_meter_daily.main virtuosi_hall

# 同步所有電表
python -m marts.campus_meter_daily.main all
```

### 執行數據彙整 (STG)
```bash
# 計算校內與共善樓的每日用電量
python -m marts.meter_campus_meter_daily.main all
```

---

## ⚠️ 注意事項與保險機制

1.  **時間邊界限制**：為確保數據完整性，系統預設僅抓取並計算至「昨日 (Yesterday)」為止。今日 (Today) 的資料因尚未結算完整 24 小時，會於明日自動補齊。
2.  **API 認證**：共善樓 API 使用校內虛擬 IP (`172.18.5.109`)，執行環境必須處於校內網域。
3.  **無功電量 (kvarh)**：部分新大樓設備（如共善樓）若 API 未提供 kvarh，系統會自動以 `NULL` 處理，避免強行補 0 造成統計誤導。
