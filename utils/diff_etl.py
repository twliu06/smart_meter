import pandas as pd
from psycopg2.extras import execute_batch
from datetime import datetime
import pendulum
from utils.db_raw import get_conn as get_raw_conn, get_engine as get_raw_engine
from utils.db_stg import get_conn as get_stg_conn, get_engine as get_stg_engine

def run_diff_etl(
    df: pd.DataFrame,
    table_name: str,
    key_cols: list[str],
    compare_cols: list[str],
    print_log,
    db_type: str = "raw"
):
    """
    共用 Diff-based ETL
    - df：已整理完成、欄位名稱 = DB 欄位
    """

    # =========================
    # 1️⃣ 讀 DB + 開 transaction
    # =========================
    engine = get_raw_engine() if db_type == "raw" else get_stg_engine()
    conn_func = get_raw_conn if db_type == "raw" else get_stg_conn
    conn = conn_func(autocommit=False)
    
    # 先讀 DB
    select_cols = key_cols + compare_cols
    sql = f"SELECT {', '.join(select_cols)} FROM {table_name}"
    try:
        db_df = pd.read_sql(sql, engine)
    except Exception as e:
        print_log(f"❌ 讀取 DB 失敗: {e}")
        raise  # 讓 transaction rollback

    # =========================
    # 2️⃣ 比對
    # =========================
    if db_df.empty:
        insert_df = df.copy()
        update_df = pd.DataFrame()
    else:
        merged = df.merge(
            db_df,
            on=key_cols,
            how="left",
            suffixes=("", "_db"),
            indicator=True,
        )

        insert_df = merged[merged["_merge"] == "left_only"].copy()
        both_df = merged[merged["_merge"] == "both"].copy()

        diff_mask = False
        for col in compare_cols:
            left = both_df[col]
            right = both_df[f"{col}_db"]
            diff_mask |= ~((left == right) | (left.isna() & right.isna()))

        update_df = both_df[diff_mask].copy()

    # =========================
    # 3️⃣ 寫 DB
    # =========================
    if insert_df.empty and update_df.empty:
        print_log("⏸️ 無任何異動，資料完全一致")
        return

    local_tz = pendulum.timezone("Asia/Taipei")
    now_ts = pendulum.now(local_tz)
    # print(f"現在台灣時間: {now_ts}")

    # ===== INSERT =====
    if not insert_df.empty:
        insert_cols = key_cols + compare_cols + ["created_at", "updated_at"]
        insert_df["created_at"] = now_ts
        insert_df["updated_at"] = now_ts

        insert_sql = f"""
            INSERT INTO {table_name} ({", ".join(insert_cols)})
            VALUES ({", ".join([f"%({c})s" for c in insert_cols])})
        """
        
        try:
            with conn.cursor() as cur:
                execute_batch(
                    cur,
                    insert_sql,
                    insert_df[insert_cols].to_dict("records"),
                )
                print_log(f"➕ INSERT {len(insert_df)} 筆")
            
            conn.commit()
    
        except Exception as e:
            conn.rollback()
            print_log(f"❌ 寫入失敗：{e}")
            raise

        finally:
            conn.close()
    
    # ===== UPDATE =====
    if not update_df.empty:
        update_df["updated_at"] = now_ts

        set_sql = ", ".join(
            [f"{c} = %({c})s" for c in compare_cols]
            + ["updated_at = %(updated_at)s"]
        )
        where_sql = " AND ".join([f"{k} = %({k})s" for k in key_cols])
        update_sql = f"""
            UPDATE {table_name}
            SET {set_sql}
            WHERE {where_sql}
        """

        try:
            with conn.cursor() as cur:
                execute_batch(
                    cur,
                    update_sql,
                    update_df[key_cols + compare_cols + ["updated_at"]].to_dict("records"),
                )
                print_log(f"🔄 UPDATE {len(update_df)} 筆")
            
            conn.commit()
    
        except Exception as e:
            conn.rollback()
            print_log(f"❌ 寫入失敗：{e}")
            raise

        finally:
            conn.close()