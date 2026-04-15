import pandas as pd
from app.repositories.security_repository import fetch_security_logs


def load_security_logs():
    try:
        df = fetch_security_logs()

        if df.empty:
            return pd.DataFrame()

        # timestamp parse
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

        if "status_code" in df.columns:
            df["status_code"] = pd.to_numeric(df["status_code"], errors="coerce")

        if "latency_ms" in df.columns:
            df["latency_ms"] = pd.to_numeric(df["latency_ms"], errors="coerce")

        return df.dropna(subset=["status_code"])

    except Exception as e:
        print("load_security_logs hatası:", e)
        return pd.DataFrame()


def get_security_summary():
    df = load_security_logs()

    if df.empty:
        return {
            "total_logs": 0,
            "top_error_types": {},
            "top_status_codes": {},
            "top_root_causes": {}
        }

    top_error_types = (
        df["error_type"].value_counts().head(5).to_dict()
        if "error_type" in df.columns else {}
    )

    top_status_codes = (
        df["status_code"].value_counts().head(5).to_dict()
        if "status_code" in df.columns else {}
    )

    top_root_causes = (
        df["root_cause"].value_counts().head(5).to_dict()
        if "root_cause" in df.columns else {}
    )

    return {
        "total_logs": len(df),
        "top_error_types": top_error_types,
        "top_status_codes": top_status_codes,
        "top_root_causes": top_root_causes
    }


def get_security_chart_data():
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

    latency_chart = {"x": [], "y": []}
    if "timestamp" in df.columns and "latency_ms" in df.columns:
        latency_df = df.dropna(subset=["timestamp", "latency_ms"]).copy()
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