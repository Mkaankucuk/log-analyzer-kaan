import pandas as pd
from app.repositories.db import get_db_connection


def fetch_request_logs():
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM request_logs", conn)
        print("DB'den gelen veri:")
        print(df.head())
        print(df.dtypes)
        return df
    finally:
        conn.close()