import psutil


def get_dashboard_data(failed_logins, successful_logins):
    total_logs = 0
    error_logs = 0
    warning_logs = 0

    failed_login_count = len(failed_logins)
    successful_login_count = len(successful_logins)

    total_login_attempts = failed_login_count + successful_login_count
    failed_login_rate = (
        (failed_login_count / total_login_attempts) * 100
        if total_login_attempts > 0 else 0
    )

    cpu_usage = int(psutil.cpu_percent(interval=1))
    memory_usage = int(psutil.virtual_memory().percent)

    if cpu_usage == 100:
        cpu_class = "cpu-high"
    elif cpu_usage >= 50:
        cpu_class = "cpu-medium"
    else:
        cpu_class = "cpu-low"

    if memory_usage == 100:
        memory_class = "memory-high"
    elif memory_usage >= 50:
        memory_class = "memory-medium"
    else:
        memory_class = "memory-low"

    process_list = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
        try:
            process_list.append({
                "name": proc.info["name"],
                "cpu": proc.info["cpu_percent"],
                "memory": round(proc.info["memory_info"].rss / (1024 * 1024), 2)
            })
        except Exception:
            pass

    top_processes = sorted(process_list, key=lambda x: x["cpu"], reverse=True)[:5]

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