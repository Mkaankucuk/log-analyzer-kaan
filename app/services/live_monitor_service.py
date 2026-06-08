"""In-memory live log stream with lightweight anomaly detection."""

from __future__ import annotations

import random
import threading
import time
import uuid
from collections import Counter, deque
from typing import Any

MAX_EVENTS = 80
MAX_ALARMS = 60
RECENT_WINDOW = 12
ERROR_SPIKE_THRESHOLD = 4
LATENCY_REPORT_INTERVAL_SECONDS = 300
THROUGHPUT_BUCKET_SECONDS = 180
LATENCY_WINDOW_SECONDS = 300
LATENCY_AVG_THRESHOLD_MS = 400
LATENCY_MAX_THRESHOLD_MS = 1000
LATENCY_ERROR_RATE_THRESHOLD_PCT = 20

_lock = threading.Lock()
_events: deque[dict[str, Any]] = deque(maxlen=MAX_EVENTS)
_alarms: deque[dict[str, Any]] = deque(maxlen=MAX_ALARMS)
_last_event_id: str | None = None
_last_alarm_id: str | None = None
_generator_started = False
_last_latency_report: dict[str, Any] = {
    "time": "-",
    "status": "pending",
    "avg_latency_ms": 0,
    "max_latency_ms": 0,
    "error_rate_pct": 0,
    "sample_count": 0,
    "window_seconds": LATENCY_WINDOW_SECONDS,
    "refresh_interval_seconds": LATENCY_REPORT_INTERVAL_SECONDS,
    "unhealthy": False,
}

_ENDPOINTS = (
    "/api/health",
    "/api/users",
    "/api/orders",
    "/api/login",
    "/api/search",
    "/api/metrics",
    "/dashboard/access-logs",
)
_METHODS = ("GET", "POST", "PUT", "DELETE")

_ANOMALY_PROFILES = (
    {"status": 503, "latency_ms": 1200, "level": "error"},
    {"status": 500, "latency_ms": 980, "level": "error"},
    {"status": 429, "latency_ms": 45, "level": "warn"},
    {"status": 401, "latency_ms": 22, "level": "warn"},
    {"status": 404, "latency_ms": 18, "level": "warn"},
    {"status": 200, "latency_ms": 1450, "level": "warn"},
)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def _severity_for_type(anomaly_type: str) -> str:
    if anomaly_type in ("server_error", "error_spike"):
        return "critical"
    return "warning"


def _alarm_message(anomaly_type: str, event: dict[str, Any]) -> str:
    method = event.get("method", "?")
    endpoint = event.get("endpoint", "?")
    status = event.get("status", "?")
    latency = event.get("latency_ms", "?")

    messages = {
        "server_error": (
            f"Sunucu hatası: {method} {endpoint} → {status} "
            f"(gecikme {latency} ms)"
        ),
        "high_latency": (
            f"Yüksek gecikme: {method} {endpoint} → {latency} ms "
            f"(durum {status})"
        ),
        "error_spike": (
            f"Hata artışı: son {RECENT_WINDOW} istekte çok sayıda 4xx/5xx"
        ),
        "auth_anomaly": (
            f"Kimlik doğrulama anomalisi: {method} {endpoint} → {status}"
        ),
        "rate_limit": (
            f"Oran sınırı: {method} {endpoint} → 429"
        ),
    }
    return messages.get(
        anomaly_type,
        f"Anomali: {method} {endpoint} (durum {status})",
    )


def _create_alarm(anomaly_type: str, event: dict[str, Any]) -> dict[str, Any] | None:
    global _last_alarm_id

    for existing in _alarms:
        if (
            not existing.get("acknowledged")
            and existing.get("type") == anomaly_type
            and existing.get("endpoint") == event.get("endpoint")
            and (time.time() - existing.get("created_at", 0)) < 25
        ):
            return None

    alarm = {
        "id": _new_id(),
        "created_at": time.time(),
        "time": _now_iso(),
        "severity": _severity_for_type(anomaly_type),
        "type": anomaly_type,
        "message": _alarm_message(anomaly_type, event),
        "event_id": event["id"],
        "method": event.get("method"),
        "endpoint": event.get("endpoint"),
        "status": event.get("status"),
        "latency_ms": event.get("latency_ms"),
        "acknowledged": False,
    }
    _alarms.appendleft(alarm)
    _last_alarm_id = alarm["id"]
    _notify_alarm_email(alarm)
    return alarm


def _notify_alarm_email(alarm: dict[str, Any]) -> None:
    """Fire-and-forget; must not run under live_monitor _lock."""
    try:
        from app.services.alert_email_service import send_major_alarm_email

        threading.Thread(
            target=send_major_alarm_email,
            args=(alarm,),
            name="major-alarm-mail",
            daemon=True,
        ).start()
    except Exception:
        pass


def _detect_anomalies(event: dict[str, Any]) -> list[str]:
    types: list[str] = []
    status = int(event.get("status", 0))
    latency = float(event.get("latency_ms", 0))

    if status >= 500:
        types.append("server_error")
    if latency >= 900:
        types.append("high_latency")
    if status in (401, 403):
        types.append("auth_anomaly")
    if status == 429:
        types.append("rate_limit")

    recent = list(_events)[:RECENT_WINDOW]
    error_count = sum(1 for e in recent if int(e.get("status", 0)) >= 400)
    if error_count >= ERROR_SPIKE_THRESHOLD:
        types.append("error_spike")

    return types


def _append_event(
    *,
    method: str,
    endpoint: str,
    status: int,
    latency_ms: float,
    level: str,
    forced_anomaly: bool = False,
) -> dict[str, Any]:
    global _last_event_id

    event = {
        "id": _new_id(),
        "ts": time.time(),
        "time": _now_iso(),
        "method": method,
        "endpoint": endpoint,
        "status": status,
        "latency_ms": round(latency_ms, 1),
        "level": level,
        "anomaly": False,
        "anomaly_types": [],
    }

    _events.appendleft(event)
    _last_event_id = event["id"]

    anomaly_types = _detect_anomalies(event)
    if forced_anomaly and not anomaly_types:
        anomaly_types = ["server_error"]

    if anomaly_types:
        event["anomaly"] = True
        event["anomaly_types"] = anomaly_types

    return event


def _generate_tick() -> None:
    method = random.choice(_METHODS)
    endpoint = random.choice(_ENDPOINTS)

    if random.random() < 0.14:
        profile = random.choice(_ANOMALY_PROFILES)
        _append_event(
            method=method,
            endpoint=endpoint,
            status=profile["status"],
            latency_ms=profile["latency_ms"],
            level=profile["level"],
            forced_anomaly=True,
        )
        return

    status = random.choices(
        [200, 201, 204, 301, 302],
        weights=[55, 10, 5, 5, 5],
    )[0]
    latency_ms = random.uniform(12, 180)
    if random.random() < 0.06:
        status = random.choice([400, 404, 408])
        latency_ms = random.uniform(20, 120)
        level = "warn"
    else:
        level = "info"

    _append_event(
        method=method,
        endpoint=endpoint,
        status=status,
        latency_ms=latency_ms,
        level=level,
    )


def _generator_loop() -> None:
    while True:
        with _lock:
            _generate_tick()
        time.sleep(1.2)


def _build_latency_report(events: list[dict[str, Any]]) -> dict[str, Any]:
    cutoff = time.time() - LATENCY_WINDOW_SECONDS
    window_events = [e for e in events if float(e.get("ts") or 0) >= cutoff]
    if not window_events:
        window_events = list(events)

    sample_count = len(window_events)
    if sample_count == 0:
        return {
            "time": _now_iso(),
            "status": "no_data",
            "avg_latency_ms": 0,
            "max_latency_ms": 0,
            "error_rate_pct": 0,
            "sample_count": 0,
            "window_seconds": LATENCY_WINDOW_SECONDS,
            "unhealthy": False,
        }

    latencies = [float(e.get("latency_ms") or 0) for e in window_events]
    errors = sum(1 for e in window_events if int(e.get("status") or 0) >= 400)
    avg_lat = sum(latencies) / sample_count
    max_lat = max(latencies)
    error_rate = (errors / sample_count) * 100

    unhealthy = (
        avg_lat >= LATENCY_AVG_THRESHOLD_MS
        or max_lat >= LATENCY_MAX_THRESHOLD_MS
        or error_rate >= LATENCY_ERROR_RATE_THRESHOLD_PCT
    )

    if unhealthy:
        status = "unhealthy"
    elif avg_lat >= LATENCY_AVG_THRESHOLD_MS * 0.7:
        status = "degraded"
    else:
        status = "healthy"

    return {
        "time": _now_iso(),
        "status": status,
        "avg_latency_ms": round(avg_lat, 1),
        "max_latency_ms": round(max_lat, 1),
        "error_rate_pct": round(error_rate, 1),
        "sample_count": sample_count,
        "window_seconds": LATENCY_WINDOW_SECONDS,
        "unhealthy": unhealthy,
    }


def _latency_monitor_loop() -> None:
    global _last_latency_report
    while True:
        with _lock:
            _last_latency_report = _build_latency_report(list(_events))
            _last_latency_report["refresh_interval_seconds"] = LATENCY_REPORT_INTERVAL_SECONDS
        time.sleep(LATENCY_REPORT_INTERVAL_SECONDS)


def ensure_generator_running() -> None:
    global _generator_started
    with _lock:
        if _generator_started:
            return
        _generator_started = True

    threading.Thread(
        target=_generator_loop,
        name="live-log-generator",
        daemon=True,
    ).start()


def get_latency_report() -> dict[str, Any]:
    ensure_generator_running()
    with _lock:
        return dict(_last_latency_report)


def _event_time_label(event: dict[str, Any]) -> str:
    label = event.get("time") or ""
    if " " in label:
        return label.split(" ", 1)[1]
    return label


def get_live_charts(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate in-memory events for Plotly charts (newest events in deque index 0)."""
    chronological = list(reversed(events))
    recent = chronological[-50:]

    latency_x = [_event_time_label(e) for e in recent]
    latency_y = [float(e.get("latency_ms") or 0) for e in recent]

    status_counter = Counter(str(int(e.get("status") or 0)) for e in events)
    method_counter = Counter(str(e.get("method") or "?") for e in events)

    stream_x = latency_x
    stream_errors = [
        1 if int(e.get("status") or 0) >= 400 else 0 for e in recent
    ]
    stream_ok = [0 if err else 1 for err in stream_errors]

    buckets: dict[int, int] = {}
    for ev in chronological:
        bucket = int(ev.get("ts") or 0) // THROUGHPUT_BUCKET_SECONDS * THROUGHPUT_BUCKET_SECONDS
        buckets[bucket] = buckets.get(bucket, 0) + 1
    sorted_buckets = sorted(buckets.items())
    throughput_x = [
        time.strftime("%H:%M:%S", time.localtime(b)) for b, _ in sorted_buckets
    ]
    throughput_y = [count for _, count in sorted_buckets]

    return {
        "latency_chart": {"x": latency_x, "y": latency_y},
        "status_chart": {
            "x": list(status_counter.keys()),
            "y": list(status_counter.values()),
        },
        "method_chart": {
            "x": list(method_counter.keys()),
            "y": list(method_counter.values()),
        },
        "stream_chart": {
            "x": stream_x,
            "errors": stream_errors,
            "ok": stream_ok,
        },
        "throughput_chart": {"x": throughput_x, "y": throughput_y},
    }


def get_snapshot(
    since_event_id: str | None = None,
    since_alarm_id: str | None = None,
) -> dict[str, Any]:
    ensure_generator_running()

    from app.services.alarm_job_service import get_job_status, list_alarms

    with _lock:
        events = list(_events)
    alarms = list_alarms(include_acknowledged=True)
    job_status = get_job_status()
    try:
        from app.services.alert_email_service import get_mail_outbox, get_mail_status

        mail_outbox = get_mail_outbox()
        mail_status = get_mail_status()
    except Exception:
        mail_outbox = []
        mail_status = {"smtp_ready": False, "enabled": False}

    new_events: list[dict[str, Any]] = []
    if since_event_id:
        seen = False
        for ev in events:
            if ev["id"] == since_event_id:
                seen = True
                continue
            if seen:
                new_events.append(ev)
        if not seen:
            new_events = events[:15]
    else:
        new_events = events[:25]

    new_alarms: list[dict[str, Any]] = []
    if since_alarm_id:
        seen = False
        for al in alarms:
            if al["id"] == since_alarm_id:
                seen = True
                continue
            if seen:
                new_alarms.append(al)
        if not seen:
            new_alarms = [a for a in alarms if not a.get("acknowledged")][:10]
    else:
        new_alarms = [a for a in alarms if not a.get("acknowledged")][:20]

    last_alarm_id = alarms[0]["id"] if alarms else _last_alarm_id
    active_alarms = job_status.get("active_alarms", 0)
    anomaly_recent = sum(1 for e in events[:20] if e.get("anomaly"))

    return {
        "ok": True,
        "events": new_events,
        "alarms": new_alarms,
        "charts": get_live_charts(events),
        "mail_outbox": mail_outbox,
        "mail_status": mail_status,
        "alarm_job": job_status,
        "stats": {
            "buffer_size": len(events),
            "active_alarms": active_alarms,
            "total_alarms": job_status.get("total_alarms", len(alarms)),
            "recent_anomalies": anomaly_recent,
            "last_event_id": _last_event_id,
            "last_alarm_id": last_alarm_id,
        },
    }


def acknowledge_alarms(alarm_ids: list[str]) -> int:
    from app.services.alarm_job_service import acknowledge_alarms as ack_job

    return ack_job(alarm_ids)


def get_buffer_stats() -> dict[str, Any]:
    from app.services.alarm_job_service import get_alarm_stats

    ensure_generator_running()
    with _lock:
        events = list(_events)
    alarm_stats = get_alarm_stats()
    return {
        "buffer_size": len(events),
        "active_alarms": alarm_stats.get("active_alarms", 0),
        "recent_anomalies": sum(1 for e in events[:20] if e.get("anomaly")),
    }
