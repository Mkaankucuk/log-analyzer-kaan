from pathlib import Path
import time
import pandas as pd
from flask import current_app

from app.repositories.log_repository import fetch_request_logs


_CACHE_TTL_SECONDS = 300
_REQUIRED_COLUMNS = ["Timestamp", "latency", "status", "method", "endpoint"]
_cached_df = pd.DataFrame()
_cache_timestamp = 0.0
_cache_db_mtime = None
_cached_filter_options = {
    "methods": [],
    "endpoints": [],
    "status_codes": []
}


def _empty_chart_data():
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


def _read_db_mtime():
    db_path = current_app.config.get("DB_PATH")
    if not db_path:
        return None

    path = Path(db_path)
    if not path.exists():
        return None

    return path.stat().st_mtime


def _prepare_request_logs():
    try:
        df = fetch_request_logs()

        if df.empty:
            return pd.DataFrame()

        if "metod" in df.columns:
            df.rename(columns={"metod": "method"}, inplace=True)

        for col in _REQUIRED_COLUMNS:
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


def load_request_logs():
    global _cached_df
    global _cache_timestamp
    global _cache_db_mtime

    current_time = time.time()
    db_mtime = _read_db_mtime()
    is_cache_fresh = (current_time - _cache_timestamp) < _CACHE_TTL_SECONDS
    is_same_db = db_mtime == _cache_db_mtime

    if not _cached_df.empty and is_cache_fresh and is_same_db:
        return _cached_df

    _cached_df = _prepare_request_logs()
    _cache_timestamp = current_time
    _cache_db_mtime = db_mtime
    _refresh_filter_options_cache(_cached_df)
    return _cached_df


def _refresh_filter_options_cache(df):
    global _cached_filter_options
    if df.empty:
        _cached_filter_options = {
            "methods": [],
            "endpoints": [],
            "status_codes": []
        }
        return

    _cached_filter_options = {
        "methods": sorted(df["method"].dropna().unique().tolist()),
        "endpoints": sorted(df["endpoint"].dropna().unique().tolist()),
        "status_codes": sorted(df["status"].dropna().astype(int).unique().tolist())
    }


def get_access_filter_options():
    load_request_logs()
    return _cached_filter_options


def get_chart_data(methods=None, status_group=None, status_code=None, endpoint=None, interval="hour"):
    df = load_request_logs()

    if df.empty:
        return _empty_chart_data()

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
        return _empty_chart_data()

    df = df.copy()
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