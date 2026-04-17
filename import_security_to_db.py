import sqlite3
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "data" / "afid_dataset_modified.csv"
DB_PATH = BASE_DIR / "logs.db"
TABLE_NAME = "security_logs"


def main():
    df = pd.read_csv(CSV_PATH)

    
    df.columns = [col.strip().lower() for col in df.columns]

    conn = sqlite3.connect(DB_PATH)
    df.to_sql(TABLE_NAME, conn, if_exists="replace", index=False)
    conn.close()

    print("Security dataset DB'ye aktarıldı.")
    print("Satır sayısı:", len(df))
    print(df.head())


if __name__ == "__main__":
    main()