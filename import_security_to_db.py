import sqlite3
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent

REAL_CSV_PATH = BASE_DIR / "data" / "afid_dataset_modified.csv"
FAKE_CSV_PATH = BASE_DIR / "data" / "fake_security_logs.csv"

DB_PATH = BASE_DIR / "logs.db"
TABLE_NAME = "security_logs"


def read_security_csv(file_path):
    if not file_path.exists():
        print(f"Dosya bulunamadı: {file_path}")
        return pd.DataFrame()

    df = pd.read_csv(file_path)

    df.columns = [col.strip().lower() for col in df.columns]

    # temel kolon kontrolü
    required_cols = [
        "timestamp",
        "method",
        "endpoint",
        "status_code",
        "error_type",
        "root_cause",
        "latency_ms"
    ]

    for col in required_cols:
        if col not in df.columns:
            print(f"{file_path.name} içinde eksik kolon: {col}")
            return pd.DataFrame()

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["status_code"] = pd.to_numeric(df["status_code"], errors="coerce")
    df["latency_ms"] = pd.to_numeric(df["latency_ms"], errors="coerce")

    df["method"] = df["method"].astype(str).str.strip().str.upper()
    df["endpoint"] = df["endpoint"].astype(str).str.strip()
    df["error_type"] = df["error_type"].astype(str).str.strip()
    df["root_cause"] = df["root_cause"].astype(str).str.strip()

    df = df.dropna(subset=["timestamp", "status_code", "latency_ms"])

    return df


def main():
    real_df = read_security_csv(REAL_CSV_PATH)
    fake_df = read_security_csv(FAKE_CSV_PATH)

    combined_df = pd.concat([real_df, fake_df], ignore_index=True)

    if combined_df.empty:
        print("Birleştirilecek security log verisi bulunamadı.")
        return

    conn = sqlite3.connect(DB_PATH)
    combined_df.to_sql(TABLE_NAME, conn, if_exists="replace", index=False)
    conn.close()

    print("Security logs DB'ye aktarıldı.")
    print("Toplam satır sayısı:", len(combined_df))
    print(combined_df.head())
    print(combined_df.dtypes)


if __name__ == "__main__":
    main()