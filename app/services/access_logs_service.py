import pandas as pd
from app.repositories.log_repository import fetch_request_logs


def load_request_logs():
    try:
        df = fetch_request_logs()

        if df.empty:
            return pd.DataFrame()

        if "metod" in df.columns:
            df.rename(columns={"metod": "method"}, inplace=True)

        required_cols = ["Timestamp", "latency", "status", "method", "endpoint"]
        for col in required_cols:
            if col not in df.columns:
                print(f"Eksik kolon: {col}")
                print("Mevcut kolonlar:", df.columns.tolist())
                return pd.DataFrame()

        df["Timestamp"] = pd.to_numeric(df["Timestamp"], errors="coerce")
        df["status"] = pd.to_numeric(df["status"], errors="coerce")
        df["latency"] = pd.to_numeric(df["latency"], errors="coerce")

        df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="s", errors="coerce")

        df["method"] = df["method"].astype(str).str.strip().str.upper()
        df["endpoint"] = df["endpoint"].astype(str).str.strip()

        df = df.dropna(subset=["Timestamp", "status", "latency"])
        df = df[df["method"] != ""]
        df = df[df["endpoint"] != ""]
        df = df[df["endpoint"].str.lower() != "nan"]

        return df

    except Exception as e:
        print("load_request_logs hatası:", e)
        return pd.DataFrame()


def get_access_filter_options():
    df = load_request_logs()

    if df.empty:
        return {
            "methods": [],
            "endpoints": [],
            "status_codes": []
        }

    methods = sorted(df["method"].dropna().unique().tolist())
    endpoints = sorted(df["endpoint"].dropna().unique().tolist())
    status_codes = sorted(df["status"].dropna().astype(int).unique().tolist())

    return {
        "methods": methods,
        "endpoints": endpoints,
        "status_codes": status_codes
    }


def get_chart_data(methods=None, status_group=None, status_code=None, endpoint=None, interval="hour"):
    df = load_request_logs()

    if df.empty:
        return {
            "method_chart_data": {},
            "request_error_chart": {
                "x": [],
                "total_requests": [],
                "error_count": []
            },
            "latency_chart": {
                "x": [],
                "avg_latency": []
            }
        }

    if methods:
        df = df[df["method"].isin(methods)]

    if status_code:
        df = df[df["status"] == int(status_code)]
    elif status_group == "2xx":
        df = df[(df["status"] >= 200) & (df["status"] < 300)]
    elif status_group == "3xx":
        df = df[(df["status"] >= 300) & (df["status"] < 400)]
    elif status_group == "4xx":
        df = df[(df["status"] >= 400) & (df["status"] < 500)]
    elif status_group == "5xx":
        df = df[(df["status"] >= 500) & (df["status"] < 600)]

    if endpoint and endpoint != "all":
        df = df[df["endpoint"] == endpoint]

    if df.empty:
        return {
            "method_chart_data": {},
            "request_error_chart": {
                "x": [],
                "total_requests": [],
                "error_count": []
            },
            "latency_chart": {
                "x": [],
                "avg_latency": []
            }
        }

    if interval == "day":
        df["bucket"] = df["Timestamp"].dt.floor("D")
    else:
        df["bucket"] = df["Timestamp"].dt.floor("h")

    methods_in_filtered = sorted(df["method"].dropna().unique().tolist())

    method_grouped = (
        df.groupby(["bucket", "method"])
        .size()
        .reset_index(name="count")
        .sort_values("bucket")
    )

    method_chart_data = {}
    for method in methods_in_filtered:
        method_df = method_grouped[method_grouped["method"] == method]
        method_chart_data[method] = {
            "x": method_df["bucket"].astype(str).tolist(),
            "y": method_df["count"].tolist()
        }

    req_err = (
        df.groupby("bucket")
        .agg(
            total_requests=("status", "count"),
            error_count=("status", lambda x: (x >= 400).sum())
        )
        .reset_index()
        .sort_values("bucket")
    )

    latency_df = (
        df.groupby("bucket")
        .agg(avg_latency=("latency", "mean"))
        .reset_index()
        .sort_values("bucket")
    )

    return {
        "method_chart_data": method_chart_data,
        "request_error_chart": {
            "x": req_err["bucket"].astype(str).tolist(),
            "total_requests": req_err["total_requests"].tolist(),
            "error_count": req_err["error_count"].tolist()
        },
        "latency_chart": {
            "x": latency_df["bucket"].astype(str).tolist(),
            "avg_latency": [round(v, 2) for v in latency_df["avg_latency"].tolist()]
        }
    }