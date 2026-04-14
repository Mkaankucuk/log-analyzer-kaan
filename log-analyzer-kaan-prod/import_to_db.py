from pathlib import Path
import sqlite3
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CSV_PATH = DATA_DIR / "requestlogs_clean3.csv"
DB_PATH = BASE_DIR / "logs.db"
TABLE_NAME = "request_logs"


def load_csv_file(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, sep=";", encoding="utf-8")

    if "metod" in df.columns:
        df.rename(columns={"metod": "method"}, inplace=True)

    df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="s", errors="coerce")
    df["status"] = pd.to_numeric(df["status"], errors="coerce")
    df["latency"] = pd.to_numeric(df["latency"], errors="coerce")

    if "method" in df.columns:
        df["method"] = df["method"].astype(str).str.strip().str.upper()

    if "endpoint" in df.columns:
        df["endpoint"] = df["endpoint"].astype(str).str.strip()

    df = df.dropna(subset=["Timestamp", "status", "latency"])

    return df


def write_to_sqlite(df: pd.DataFrame, db_path: Path, table_name: str) -> None:
    conn = sqlite3.connect(db_path)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()


def main():
    if not CSV_PATH.exists():
        print(f"CSV dosyası bulunamadı: {CSV_PATH}")
        return

    df = load_csv_file(CSV_PATH)

    print("Kolonlar:", df.columns.tolist())
    print(df.head())
    print("Satır sayısı:", len(df))

    write_to_sqlite(df, DB_PATH, TABLE_NAME)

    print(" Veri başarıyla SQLite içine aktarıldı.")
    print(f"DB yolu: {DB_PATH}")


if __name__ == "__main__":
    main()