from app.repositories.db import get_db_connection


def get_request_log_count():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM request_logs")
        row = cur.fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def get_request_log_preview(limit=5):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM request_logs LIMIT ?", (limit,))
        return cur.fetchall()
    finally:
        conn.close()
