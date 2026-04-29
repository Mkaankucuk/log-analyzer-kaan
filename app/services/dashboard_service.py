import psutil
import time
from app.repositories.security_repository import fetch_security_log_counts


IGNORED_PROCESS_NAMES = {
    "system idle process",
    "idle",
}

_PROCESS_CACHE_TTL_SECONDS = 4
_process_cache = {
    "timestamp": 0.0,
    "top_processes": []
}


def _usage_class(usage_value, prefix):
    if usage_value == 100:
        return f"{prefix}-high"
    if usage_value >= 50:
        return f"{prefix}-medium"
    return f"{prefix}-low"


def _collect_top_processes(limit=5):
    process_list = []
    cpu_count = psutil.cpu_count(logical=True) or 1

    for proc in psutil.process_iter(["name", "cpu_percent", "memory_info"]):
        try:
            process_name = (proc.info.get("name") or "").strip()
            if not process_name or process_name.lower() in IGNORED_PROCESS_NAMES:
                continue

            raw_cpu_percent = float(proc.info.get("cpu_percent") or 0.0)
            normalized_cpu = min(100.0, raw_cpu_percent / cpu_count)
            memory_info = proc.info.get("memory_info")
            memory_mb = round((memory_info.rss / (1024 * 1024)) if memory_info else 0.0, 2)

            process_list.append({
                "name": process_name,
                "cpu": round(normalized_cpu, 2),
                "memory": memory_mb
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return sorted(process_list, key=lambda x: x["cpu"], reverse=True)[:limit]


def _get_top_processes_cached():
    now = time.time()
    if now - _process_cache["timestamp"] < _PROCESS_CACHE_TTL_SECONDS:
        return _process_cache["top_processes"]

    top_processes = _collect_top_processes(limit=5)
    _process_cache["timestamp"] = now
    _process_cache["top_processes"] = top_processes
    return top_processes


def get_dashboard_data(failed_logins, successful_logins):
    log_counts = fetch_security_log_counts()
    total_logs = log_counts["total_logs"]
    error_logs = log_counts["error_logs"]
    warning_logs = log_counts["warning_logs"]

    failed_login_count = len(failed_logins)
    successful_login_count = len(successful_logins)

    total_login_attempts = failed_login_count + successful_login_count
    failed_login_rate = (
        (failed_login_count / total_login_attempts) * 100
        if total_login_attempts > 0 else 0
    )

    # interval>0 ensures real measurement instead of stale 0 values.
    cpu_usage = int(psutil.cpu_percent(interval=0.4))
    memory_usage = int(psutil.virtual_memory().percent)

    cpu_class = _usage_class(cpu_usage, "cpu")
    memory_class = _usage_class(memory_usage, "memory")

    top_processes = _get_top_processes_cached()

    return {
        "total_logs": total_logs,
        "error_logs": error_logs,
        "warning_logs": warning_logs,
        "failed_login_count": failed_login_count,
        "failed_login_rate": round(failed_login_rate, 2),
        "cpu_usage": cpu_usage,
        "cpu_class": cpu_class,
        "memory_usage": memory_usage,
        "memory_class": memory_class,
        "failed_logins": failed_logins,
        "successful_logins": successful_logins,
        "top_processes": top_processes
    }