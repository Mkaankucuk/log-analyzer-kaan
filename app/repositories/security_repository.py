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