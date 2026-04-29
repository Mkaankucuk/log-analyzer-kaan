from pathlib import Path
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_PATH = BASE_DIR / "data" / "requestlogs_clean3.csv"
OUTPUT_PATH = BASE_DIR / "data" / "requestlogs_generated.csv"


def _load_clean_access_logs():
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(f"Kaynak dosya bulunamadi: {SOURCE_PATH}")

    df = pd.read_csv(SOURCE_PATH, sep=";")
    df.columns = ["Timestamp", "latency", "status", "method", "endpoint"]
    df = df[df["Timestamp"] != "Timestamp"]

    df["Timestamp"] = pd.to_numeric(df["Timestamp"], errors="coerce")
    df["latency"] = pd.to_numeric(df["latency"], errors="coerce")
    df["status"] = pd.to_numeric(df["status"], errors="coerce")
    df["method"] = df["method"].astype(str).str.strip().str.upper()
    df["endpoint"] = df["endpoint"].astype(str).str.strip()
    df = df.dropna(subset=["Timestamp", "latency", "status", "method", "endpoint"])

    return df


def generate_access_logs(row_count=None, random_state=42):
    clean_df = _load_clean_access_logs()

    if clean_df.empty:
        return pd.DataFrame(columns=["Timestamp", "latency", "status", "method", "endpoint"])

    if row_count is None:
        row_count = len(clean_df)

    replace = row_count > len(clean_df)
    # requestlogs_clean3 ile ayni karakterde veri uretmek icin kaynaktan ornekleme yapilir.
    sampled = clean_df.sample(n=row_count, replace=replace, random_state=random_state).reset_index(drop=True)
    sampled["latency"] = sampled["latency"].round().astype(int)
    sampled["status"] = sampled["status"].round().astype(int)
    sampled["Timestamp"] = sampled["Timestamp"].astype(float)
    return sampled


def save_access_logs(df):
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    df.to_csv(OUTPUT_PATH, sep=";", index=False)

    print(f"Generated access logs olusturuldu: {OUTPUT_PATH}")


if __name__ == "__main__":
    dataframe = generate_access_logs()
    save_access_logs(dataframe)