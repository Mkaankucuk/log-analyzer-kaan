import pandas as pd
from app.repositories.security_repository import fetch_security_logs


def load_security_logs():
    try:
        df = fetch_security_logs()

        if df.empty:
            return pd.DataFrame()

        # kolon isimlerini normalize et
        df.columns = [col.strip().lower() for col in df.columns]

        if "timestamp" not in df.columns or "latency_ms" not in df.columns:
            print("Gerekli kolonlar yok:", df.columns.tolist())
            return pd.DataFrame()

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df["latency_ms"] = pd.to_numeric(df["latency_ms"], errors="coerce")

        df = df.dropna(subset=["timestamp", "latency_ms"])

        print("Security logs temiz veri boyutu:", df.shape)
        print(df[["timestamp", "latency_ms"]].head())

        return df

    except Exception as e:
        print("load_security_logs hatası:", e)
        return pd.DataFrame()


def get_security_summary():
    df = load_security_logs()

    if df.empty:
        return {"total_logs": 0}

    return {"total_logs": len(df)}


def get_security_chart_data(interval="hour"):
    df = load_security_logs()

    if df.empty:
        return {
            "status_chart": {"x": [], "y": []},
            "error_type_chart": {"x": [], "y": []},
            "latency_chart": {"x": [], "y": []}
        }

    status_chart = {"x": [], "y": []}
    if "status_code" in df.columns:
        status_counts = df["status_code"].value_counts().sort_index()
        status_chart = {
            "x": [str(x) for x in status_counts.index.tolist()],
            "y": status_counts.tolist()
        }

    error_type_chart = {"x": [], "y": []}
    if "error_type" in df.columns:
        error_counts = df["error_type"].value_counts().head(10)
        error_type_chart = {
            "x": error_counts.index.tolist(),
            "y": error_counts.tolist()
        }

    latency_df = df.copy()

    if interval == "day":
        latency_df["bucket"] = latency_df["timestamp"].dt.floor("D")
    else:
        latency_df["bucket"] = latency_df["timestamp"].dt.floor("h")

    grouped = (
        latency_df.groupby("bucket")
        .agg(avg_latency=("latency_ms", "mean"))
        .reset_index()
        .sort_values("bucket")
    )

    latency_chart = {
        "x": grouped["bucket"].astype(str).tolist(),
        "y": [round(v, 2) for v in grouped["avg_latency"].tolist()]
    }

    return {
        "status_chart": status_chart,
        "error_type_chart": error_type_chart,
        "latency_chart": latency_chart
    }