import sqlite3
from pathlib import Path


def get_db_connection():
    base_dir = Path(__file__).resolve().parents[2]
    db_path = base_dir / "logs.db"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn