from utils.db_raw import get_engine as get_raw_engine
from utils.db_stg import get_engine as get_stg_engine
import pandas as pd

# 預設跳過的設備
SKIP_METERS = {"A12", "H01", "H02"}

def get_last_date(table_name: str, db_type: str = "raw", date_col: str = "meter_data_timestamp", meter_id: str = None):
    """
    取得 raw table 最大日期，可指定特定的 meter_id
    """
    engine = get_raw_engine() if db_type == "raw" else get_stg_engine()
    sql = f"SELECT MAX({date_col})::date AS last_date FROM {table_name}"

    # 如果有指定 meter_id，加入 WHERE 條件
    if meter_id:
        sql += f" WHERE meter_id = '{meter_id}'"
    
    try:
        df = pd.read_sql(sql, engine)
        return df.loc[0, "last_date"]
    except Exception as e:
        print(f"⚠️ get_last_date 執行失敗 ({table_name}, {meter_id}): {e}")
        return None

def get_meter_ids(device_table: str = "sensor.campus_meter_device") -> list[str]:
    """
    取得所有設備 ID
    """
    engine = get_raw_engine()
    sql = f"SELECT device_id FROM {device_table}"
    df = pd.read_sql(sql, engine)
    return df["device_id"].tolist()
