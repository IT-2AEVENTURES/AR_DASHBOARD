import pandas as pd
from app.data.db import get_connection

def build_where_clause(filters: dict, snapshot_id: str, table_alias: str = "") -> tuple:
    """Build WHERE clause and params array for duckdb query."""
    prefix = f"{table_alias}." if table_alias else ""
    where_parts = [f"{prefix}snapshot_id = ?"]
    params = [snapshot_id]
    
    if not filters:
        return "WHERE " + " AND ".join(where_parts), params
        
    for key in ["ar_person", "sales_person_code", "name"]:
        if filters.get(key):
            v = filters[key]
            if isinstance(v, list) and len(v) > 0:
                if "__NONE__" in v:
                    continue
                placeholders = ",".join(["?"] * len(v))
                where_parts.append(f"{prefix}{key} IN ({placeholders})")
                params.extend(v)
            elif isinstance(v, str) and v not in ["All", "__NONE__"]:
                where_parts.append(f"{prefix}{key} = ?")
                params.append(v)

    where_sql = "WHERE " + " AND ".join(where_parts)
    return where_sql, params

def get_filter_options(snapshot_id: str, filters: dict = None) -> dict:
    """Sử dụng bảng con mart_filters để tăng tốc độ load dropdown (Data Marts)"""
    if not snapshot_id:
        return {"ar_person": [], "sales_person_code": [], "name": []}
        
    conn = get_connection()
    try:
        # 1. AR Person (Root level - ALWAYS shows all options for the snapshot)
        ar_query = "SELECT DISTINCT ar_person FROM mart_filters WHERE snapshot_id = ? ORDER BY 1"
        ar_persons = conn.execute(ar_query, [snapshot_id]).df()["ar_person"].tolist()
        
        # 2. Sales Person (Depends ONLY on AR Person selection)
        sales_filters = {"ar_person": filters.get("ar_person")} if filters else {}
        sales_where, sales_params = build_where_clause(sales_filters, snapshot_id)
        sales_query = f"SELECT DISTINCT sales_person_code FROM mart_filters {sales_where} ORDER BY 1"
        sales_persons = conn.execute(sales_query, sales_params).df()["sales_person_code"].tolist()
        
        # 3. Customer (Depends ONLY on AR Person and Sales Person selections)
        cust_filters = {"ar_person": filters.get("ar_person"), "sales_person_code": filters.get("sales_person_code")} if filters else {}
        cust_where, cust_params = build_where_clause(cust_filters, snapshot_id)
        cust_query = f"SELECT DISTINCT name FROM mart_filters {cust_where} ORDER BY 1"
        customers = conn.execute(cust_query, cust_params).df()["name"].tolist()
        
        return {
            "ar_person": [str(x) for x in ar_persons if pd.notnull(x)],
            "sales_person_code": [str(x) for x in sales_persons if pd.notnull(x)],
            "name": [str(x) for x in customers if pd.notnull(x)]
        }
    except Exception as e:
        print(f"Error in get_filter_options: {e}")
        return {"ar_person": [], "sales_person_code": [], "name": []}
    finally:
        conn.close()

def get_summary_metrics(snapshot_id: str, filters: dict) -> dict:
    if not snapshot_id:
        return {"total_ar": 0, "balance_overdue": 0, "pct_overdue": 0.0, "total_customers": 0}
        
    where_sql, params = build_where_clause(filters, snapshot_id)
    
    query = f"""
        SELECT 
            SUM(bal_due) as total_ar,
            SUM(total_amt_overdue) as balance_overdue,
            COUNT(DISTINCT name) as total_customers
        FROM fact_ar
        {where_sql}
    """
    
    conn = get_connection()
    try:
        df = conn.execute(query, params).fetchdf()
        if not df.empty:
            total_ar = float(df.iloc[0]["total_ar"] or 0)
            balance_overdue = float(df.iloc[0]["balance_overdue"] or 0)
            pct_overdue = balance_overdue / total_ar if total_ar > 0 else 0.0
            total_customers = int(df.iloc[0]["total_customers"] or 0)
            return {
                "total_ar": total_ar,
                "balance_overdue": balance_overdue,
                "pct_overdue": pct_overdue,
                "total_customers": total_customers
            }
    except Exception as e:
        print("Metrics error:", e)
    finally:
        conn.close()
        
    return {"total_ar": 0, "balance_overdue": 0, "pct_overdue": 0.0, "total_customers": 0}

def get_trend_data(snapshot_id: str, filters: dict = None) -> pd.DataFrame:
    # Unified trend limited to the 7 most recent periods
    where_parts = [
        """
        h.snapshot_id IN (
            SELECT snapshot_id 
            FROM import_history 
            ORDER BY imported_at DESC 
            LIMIT 7
        )
        """
    ]
    params = []
    
    if filters:
        for key in ["ar_person", "sales_person_code", "name"]:
            if filters.get(key):
                v = filters[key]
                if isinstance(v, list) and len(v) > 0:
                    if "__NONE__" in v:
                        continue
                    placeholders = ",".join(["?"] * len(v))
                    where_parts.append(f"f.{key} IN ({placeholders})")
                    params.extend(v)
                elif isinstance(v, str) and v not in ["All", "__NONE__"]:
                    where_parts.append(f"f.{key} = ?")
                    params.append(v)
            
    where_sql = ""
    if where_parts:
        where_sql = "WHERE " + " AND ".join(where_parts)
        
    conn = get_connection()
    try:
        tables = [x[0] for x in conn.execute("SHOW TABLES").fetchall()]
        if 'fact_ar' not in tables or 'import_history' not in tables:
            return pd.DataFrame()
            
        cols = [x[0].lower() for x in conn.execute("DESCRIBE fact_ar").fetchall()]
        
        aging_cols = [
            '0_-_6', '7_-_13', '14_-_20', '21_-_29',
            '30_-_37', '38_-_45', '45_up', '60_up',
            # Legacy / fallback names
            '30_-_38', 'current', '1_-_30_days', '31_-_60_days',
        ]
        
        select_aging = []
        for c in aging_cols:
            if c in cols:
                select_aging.append(f'SUM(f."{c}") as "{c}"')
            else:
                select_aging.append(f'0 as "{c}"')
                
        aging_sql = ", ".join(select_aging)
        if aging_sql:
            aging_sql = ", " + aging_sql
            
        query = f"""
            SELECT 
                CAST(h.imported_at AS DATE) as snapshot_date,
                h.snapshot_type,
                SUM(f.bal_due) as total_ar,
                SUM(f.total_amt_overdue) as balance_overdue,
                SUM(f.total_amt_overdue) / NULLIF(SUM(f.bal_due), 0) as pct_overdue
                {aging_sql}
            FROM fact_ar f
            JOIN import_history h ON f.snapshot_id = h.snapshot_id
            {where_sql}
            GROUP BY CAST(h.imported_at AS DATE), h.snapshot_type
            ORDER BY snapshot_date ASC
        """
        return conn.execute(query, params).fetchdf()
    except Exception as e:
        print("Trend error:", e)
        return pd.DataFrame()
    finally:
        conn.close()
