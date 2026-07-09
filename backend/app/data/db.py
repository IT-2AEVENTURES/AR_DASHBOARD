import duckdb
import polars as pl
from datetime import datetime
import os
from app.config.settings import DB_PATH

def get_connection():
    return duckdb.connect(DB_PATH)

def init_db():
    conn = get_connection()
    # Create tables if not exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS import_history (
            snapshot_id VARCHAR PRIMARY KEY,
            file_name VARCHAR,
            imported_at TIMESTAMP,
            total_rows INTEGER,
            snapshot_type VARCHAR
        )
    """)
    conn.close()

def align_and_insert(conn, table_name: str, df_name: str):
    existing_cols = [x[0] for x in conn.execute(f"DESCRIBE {table_name}").fetchall()]
    new_cols_info = conn.execute(f"DESCRIBE {df_name}").fetchall()
    new_cols = [x[0] for x in new_cols_info]

    # Remove stale columns left over from previous imports so the table matches the
    # current normalized schema.
    for col in list(existing_cols):
        if col not in new_cols and col != "snapshot_id":
            try:
                conn.execute(f'ALTER TABLE {table_name} DROP COLUMN "{col}"')
                existing_cols.remove(col)
            except Exception as e:
                print(f"Schema Evolution Error: Could not drop column {col} - {e}")

    # Schema Evolution: Auto-add new columns to the database
    for i, col in enumerate(new_cols):
        if col not in existing_cols:
            col_type = new_cols_info[i][1]
            try:
                conn.execute(f'ALTER TABLE {table_name} ADD COLUMN "{col}" {col_type}')
                existing_cols.append(col)
            except Exception as e:
                print(f"Schema Evolution Error: Could not add column {col} - {e}")

    select_parts = []
    for col in existing_cols:
        if col in new_cols:
            select_parts.append(f'"{col}"')
        else:
            select_parts.append(f'NULL AS "{col}"')

    query = f"INSERT INTO {table_name} SELECT {', '.join(select_parts)} FROM {df_name}"
    conn.execute(query)

def load_data(raw_df: pl.DataFrame, fact_df: pl.DataFrame, file_name: str, snapshot_type: str = 'adhoc', custom_imported_at=None):
    """
    Append or Replace (Upsert) raw_ar and fact_ar into DuckDB.
    If the file_name already exists, delete old records and insert new ones.
    Records metadata in import_history.
    """
    init_db()
    conn = get_connection()
    
    try:
        snapshot_id = file_name # Use file_name as unique identifier
        imported_at = custom_imported_at if custom_imported_at else datetime.now()
        total_rows = fact_df.shape[0]
        
        # UPSERT Logic: Check and Delete existing
        existing = conn.execute("SELECT snapshot_id FROM import_history WHERE snapshot_id = ?", [snapshot_id]).fetchone()
        if existing:
            conn.execute("DELETE FROM import_history WHERE snapshot_id = ?", [snapshot_id])
            try:
                conn.execute("DELETE FROM raw_ar WHERE snapshot_id = ?", [snapshot_id])
                conn.execute("DELETE FROM fact_ar WHERE snapshot_id = ?", [snapshot_id])
            except duckdb.CatalogException:
                pass
                
        # Auto-cleanup of daily snapshots when importing a monthly snapshot
        if snapshot_type == 'monthly':
            import re
            m = re.search(r"MONTH_(\d+)", file_name)
            if m:
                month_num = m.group(1)
                daily_pattern = f"%MONTH\\_{month_num}\\_DAY\\_%"
                conn.execute("DELETE FROM import_history WHERE snapshot_id LIKE ? ESCAPE '\\'", [daily_pattern])
                try:
                    conn.execute("DELETE FROM raw_ar WHERE snapshot_id LIKE ? ESCAPE '\\'", [daily_pattern])
                    conn.execute("DELETE FROM fact_ar WHERE snapshot_id LIKE ? ESCAPE '\\'", [daily_pattern])
                    conn.execute("DELETE FROM mart_filters WHERE snapshot_id LIKE ? ESCAPE '\\'", [daily_pattern])
                except duckdb.CatalogException:
                    pass
        
        # Insert Metadata
        conn.execute(
            "INSERT INTO import_history VALUES (?, ?, ?, ?, ?)",
            [snapshot_id, file_name, imported_at, total_rows, snapshot_type]
        )
        
        # Add snapshot_id to dataframes
        raw_df = raw_df.with_columns(pl.lit(snapshot_id).alias("snapshot_id"))
        fact_df = fact_df.with_columns(pl.lit(snapshot_id).alias("snapshot_id"))
        
        # Append Raw Data
        conn.register("temp_raw", raw_df)
        try:
            align_and_insert(conn, "raw_ar", "temp_raw")
        except duckdb.CatalogException:
            conn.execute("CREATE TABLE raw_ar AS SELECT * FROM temp_raw")
            
        # Append Fact Data
        conn.register("temp_fact", fact_df)
        try:
            align_and_insert(conn, "fact_ar", "temp_fact")
        except duckdb.CatalogException:
            conn.execute("CREATE TABLE fact_ar AS SELECT * FROM temp_fact")
            
        # --- BUILD DATA MARTS (CHILD TABLES) ---
        # 1. mart_filters: Lưu sẵn các tổ hợp duy nhất để load UI nhanh nhất
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mart_filters (
                snapshot_id VARCHAR,
                ar_person VARCHAR,
                sales_person_code VARCHAR,
                name VARCHAR
            )
        """)
        conn.execute("DELETE FROM mart_filters WHERE snapshot_id = ?", [snapshot_id])
        conn.execute("""
            INSERT INTO mart_filters 
            SELECT DISTINCT snapshot_id, ar_person, sales_person_code, name 
            FROM temp_fact
        """)
            
    finally:
        conn.close()

def get_latest_snapshot_id():
    conn = get_connection()
    try:
        res = conn.execute("SELECT snapshot_id FROM import_history ORDER BY imported_at DESC LIMIT 1").fetchone()
        if res:
            return res[0]
    except Exception:
        pass
    finally:
        conn.close()
    return None
