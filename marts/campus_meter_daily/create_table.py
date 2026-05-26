from utils.db_raw import get_conn

TABLE_NAME = "sensor.campus_meter_daily"
TABLE_COMMENT = "校內智慧電表每日原始資料表"

# (欄位名稱, 型別, NOT NULL, 欄位註解)
COLUMNS = [
    ("id", "BIGSERIAL PRIMARY KEY", True, "智慧電表原始資料識別碼"),

    # 識別資訊
    ("meter_id", "VARCHAR(50)", True, "電表識別碼"),
    ("meter_data_timestamp", "TIMESTAMP(6)", True, "資料時間戳記"),

    # 電壓 (V)
    ("meter_voltage_r", "INT", False, "R相電壓"),
    ("meter_voltage_s", "INT", False, "S相電壓"),
    ("meter_voltage_t", "INT", False, "T相電壓"),

    # 電流 (A)
    ("meter_current_r", "NUMERIC(18,2)", False, "R相電流"),
    ("meter_current_s", "NUMERIC(18,2)", False, "S相電流"),
    ("meter_current_t", "NUMERIC(18,2)", False, "T相電流"),

    # 功率 / 電量
    ("meter_active_power_kw", "NUMERIC(18,2)", False, "瞬時功率（千瓦）"),
    ("meter_energy_kwh_total", "NUMERIC(18,2)", False, "累積用電量（千瓦時）"),
    ("meter_apparent_power_kva", "NUMERIC(18,2)", False, "視在功率"),
    ("meter_reactive_power_kvar", "NUMERIC(18,2)", False, "無功功率"),
    ("meter_energy_kvarh_total", "NUMERIC(18,2)", False, "累積無功電量"),

    # 其他電力參數
    ("meter_frequency_hz", "NUMERIC(18,2)", False, "頻率（Hz）"),
    ("meter_power_factor", "NUMERIC(18,2)", False, "功率因數"),
    ("meter_current_transform_ratio", "INT", False, "電流互感器倍率"),
    ("meter_voltage_transform_ratio", "INT", False, "電壓互感器倍率"),

    # 技術欄位
    ("created_at", "TIMESTAMP(6)", True, "資料建立時間"),
    ("updated_at", "TIMESTAMP(6)", True, "資料更新時間"),
]

# 唯一鍵，避免同一電表同一時間重複
UNIQUE_KEYS = ["meter_id", "meter_data_timestamp"]


def build_create_table_sql() -> str:
    col_defs = []

    for name, dtype, not_null, _ in COLUMNS:
        nn = " NOT NULL" if not_null and "PRIMARY KEY" not in dtype else ""
        col_defs.append(f"    {name} {dtype}{nn}")

    col_defs.append(f"    UNIQUE ({', '.join(UNIQUE_KEYS)})")

    return f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
{",\n".join(col_defs)}
);
"""


def build_comment_sql() -> list[str]:
    stmts = [
        f"COMMENT ON TABLE {TABLE_NAME} IS '{TABLE_COMMENT}';"
    ]

    for name, _, _, comment in COLUMNS:
        if comment:
            stmts.append(
                f"COMMENT ON COLUMN {TABLE_NAME}.{name} IS '{comment}';"
            )

    return stmts


def main():
    with get_conn(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(build_create_table_sql())

            for stmt in build_comment_sql():
                cur.execute(stmt)

            print(f"✅ {TABLE_NAME} 建表完成")


if __name__ == "__main__":
    main()
