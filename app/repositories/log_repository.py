import pandas as pd
from app.repositories.db import get_db_connection


def fetch_request_logs():
    conn = get_db_connection()
    try:
        return pd.read_sql_query("SELECT * FROM request_logs", conn)
    finally:
        conn.close()