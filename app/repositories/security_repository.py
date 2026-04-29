import pandas as pd
from app.repositories.db import get_db_connection


def fetch_security_logs():
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM security_logs", conn)
        print("Security logs satır sayısı:", len(df))
        return df
    finally:
        conn.close()


def fetch_security_log_counts():
    conn = get_db_connection()
    try:
        query = """
            SELECT
                COUNT(*) AS total_logs,
                SUM(CASE WHEN CAST(status_code AS INTEGER) >= 500 THEN 1 ELSE 0 END) AS error_logs,
                SUM(
                    CASE
                        WHEN CAST(status_code AS INTEGER) >= 400
                         AND CAST(status_code AS INTEGER) < 500
                        THEN 1
                        ELSE 0
                    END
                ) AS warning_logs
            FROM security_logs
        """
        df = pd.read_sql_query(query, conn)
        if df.empty:
            return {"total_logs": 0, "error_logs": 0, "warning_logs": 0}

        row = df.iloc[0]
        return {
            "total_logs": int(row.get("total_logs") or 0),
            "error_logs": int(row.get("error_logs") or 0),
            "warning_logs": int(row.get("warning_logs") or 0)
        }
    finally:
        conn.close()