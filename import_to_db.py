import sqlite3
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent

REAL_CSV_PATH = BASE_DIR / "data" / "requestlogs_clean3.csv"
FAKE_CSV_PATH = BASE_DIR / "data" / "requestlogs_generated.csv"

DB_PATH = BASE_DIR / "logs.db"
TABLE_NAME = "request_logs"


def read_access_csv(file_path):
    if not file_path.exists():
        print(f"Dosya bulunamadı: {file_path}")
        return pd.DataFrame()

    df = pd.read_csv(file_path, sep=";")

    df.columns = ["Timestamp", "latency", "status", "method", "endpoint"]

    df = df[df["Timestamp"] != "Timestamp"]

    df["Timestamp"] = pd.to_numeric(df["Timestamp"], errors="coerce")
    df["latency"] = pd.to_numeric(df["latency"], errors="coerce")
    df["status"] = pd.to_numeric(df["status"], errors="coerce")

    df["method"] = df["method"].astype(str).str.strip().str.upper()
    df["endpoint"] = df["endpoint"].astype(str).str.strip()

    df = df.dropna(subset=["Timestamp", "latency", "status", "method", "endpoint"])

    return df


def main():
    real_df = read_access_csv(REAL_CSV_PATH)
    fake_df = read_access_csv(FAKE_CSV_PATH)

    combined_df = pd.concat([real_df, fake_df], ignore_index=True)

    if combined_df.empty:
        print("Birleştirilecek access log verisi bulunamadı.")
        return

    conn = sqlite3.connect(DB_PATH)
    combined_df.to_sql(TABLE_NAME, conn, if_exists="replace", index=False)
    conn.close()

    print("Access logs DB'ye aktarıldı.")
    print("Toplam satır sayısı:", len(combined_df))
    print(combined_df.head())
    print(combined_df.dtypes)


if __name__ == "__main__":
    main()