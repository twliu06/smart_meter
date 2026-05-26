from utils.db_stg import get_conn

TABLE_NAME = "public.sensor_campus_meter_daily"
TABLE_COMMENT = "校內智慧電表每日彙整資料表（每日用電量、平均功率與功率因數）"

# (欄位名稱, 型別, NOT NULL, 欄位註解)
COLUMNS = [
    ("id", "BIGSERIAL PRIMARY KEY", True, "智慧電表每日彙整資料識別碼"),

    # 識別資訊
    ("meter_id", "VARCHAR(50)", True, "電表識別碼"),
    ("usage_date", "DATE", True, "當日用電日期"),

    # 功率 / 電量
    ("meter_daily_energy_kwh", "NUMERIC(18,2)", False, "當日用電量（千瓦時）"),
    ("meter_daily_energy_kvarh", "NUMERIC(18,2)", False, "當日累積無功電量"),

    # 技術欄位
    ("created_at", "TIMESTAMP(6)", True, "資料建立時間"),
    ("updated_at", "TIMESTAMP(6)", True, "資料更新時間"),
]

# 唯一鍵，避免同一電表同一天重複
UNIQUE_KEYS = ["meter_id", "usage_date"]


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
