import sqlite3
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "data" / "requestlogs_clean3.csv"
DB_PATH = BASE_DIR / "logs.db"
TABLE_NAME = "request_logs"


def main():
    df = pd.read_csv(CSV_PATH, sep=";")

    df.columns = ["Timestamp", "latency", "status", "method", "endpoint"]

    
    df = df[df["Timestamp"] != "Timestamp"]

    df["Timestamp"] = pd.to_numeric(df["Timestamp"], errors="coerce")
    df["latency"] = pd.to_numeric(df["latency"], errors="coerce")
    df["status"] = pd.to_numeric(df["status"], errors="coerce")

    df["method"] = df["method"].astype(str).str.strip().str.upper()
    df["endpoint"] = df["endpoint"].astype(str).str.strip()

    df = df.dropna(subset=["Timestamp", "latency", "status", "method", "endpoint"])

    conn = sqlite3.connect(DB_PATH)
    df.to_sql(TABLE_NAME, conn, if_exists="replace", index=False)
    conn.close()

    print("DB yeniden oluşturuldu.")
    print(df.head())
    print(df.dtypes)


if __name__ == "__main__":
    main()