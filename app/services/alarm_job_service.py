"""Cron-style alarm job: periodically scans DB logs, persists alarms, sends mail."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from app.services.mail_settings_service import load_mail_settings

_lock = threading.Lock()
_job_thread_started = False
_job_running = False

MAX_ALARMS = 200
MAX_FINGERPRINTS = 600
RECENT_WINDOW = 12
ERROR_SPIKE_THRESHOLD = 4
INITIAL_SCAN_LIMIT = 80
BATCH_LIMIT = 500

MAJOR_TYPES = frozenset({"server_error", "error_spike"})

_DEFAULT_JOB_STATE: dict[str, Any] = {
    "last_run_at": 0.0,
    "next_run_at": 0.0,
    "last_duration_ms": 0,
    "rows_scanned": 0,
    "alarms_created_last_run": 0,
    "last_error": None,
    "run_count": 0,
    "last_security_watermark": "",
    "last_access_watermark": "",
    "seen_fingerprints": [],
}


def _base_dir() -> Path:
    try:
        from flask import current_app

        return Path(current_app.config.get("BASE_DIR", Path(__file__).resolve().parents[2]))
    except RuntimeError:
        return Path(__file__).resolve().parents[2]


def _db_path() -> Path:
    return _base_dir() / "logs.db"


def _alarms_path() -> Path:
    data_dir = _base_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "alarms.json"


def _job_state_path() -> Path:
    data_dir = _base_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "alarm_job_state.json"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def is_job_enabled() -> bool:
    return bool(load_mail_settings().get("job_enabled", True))


def get_scan_interval_seconds() -> int:
    try:
        val = int(load_mail_settings().get("scan_interval_seconds", 300))
    except (TypeError, ValueError):
        val = 300
    return max(60, min(val, 3600))


def _severity_for_type(anomaly_type: str) -> str:
    if anomaly_type in MAJOR_TYPES:
        return "critical"
    return "warning"


def _alarm_message(anomaly_type: str, row: dict[str, Any]) -> str:
    method = row.get("method", "?")
    endpoint = row.get("endpoint", "?")
    status = row.get("status", "?")
    latency = row.get("latency_ms", "?")

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


def _load_alarms_unlocked() -> list[dict[str, Any]]:
    path = _alarms_path()
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    return raw[:MAX_ALARMS]


def _save_alarms_unlocked(alarms: list[dict[str, Any]]) -> None:
    path = _alarms_path()
    path.write_text(
        json.dumps(alarms[:MAX_ALARMS], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_job_state_unlocked() -> dict[str, Any]:
    path = _job_state_path()
    if not path.is_file():
        return dict(_DEFAULT_JOB_STATE)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(_DEFAULT_JOB_STATE)
    if not isinstance(raw, dict):
        return dict(_DEFAULT_JOB_STATE)
    state = dict(_DEFAULT_JOB_STATE)
    state.update(raw)
    fps = state.get("seen_fingerprints")
    if not isinstance(fps, list):
        state["seen_fingerprints"] = []
    return state


def _save_job_state_unlocked(state: dict[str, Any]) -> None:
    path = _job_state_path()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _format_access_time(ts_raw: Any) -> str:
    try:
        ts = float(ts_raw)
        if ts > 1_000_000_000_000:
            ts /= 1000.0
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
    except (TypeError, ValueError, OSError):
        return str(ts_raw or "")


def _normalize_row(
    *,
    source: str,
    method: str,
    endpoint: str,
    status: Any,
    latency_ms: Any,
    time_label: str,
    sort_key: str,
    row_key: str,
) -> dict[str, Any] | None:
    try:
        status_i = int(status)
        latency_f = float(latency_ms)
    except (TypeError, ValueError):
        return None

    method_s = str(method or "").strip().upper() or "?"
    endpoint_s = str(endpoint or "").strip() or "?"
    if not endpoint_s:
        return None

    return {
        "source": source,
        "method": method_s,
        "endpoint": endpoint_s,
        "status": status_i,
        "latency_ms": round(latency_f, 1),
        "time": time_label,
        "sort_key": sort_key,
        "row_key": row_key,
    }


def _fetch_log_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    db = _db_path()
    if not db.is_file():
        return []

    rows: list[dict[str, Any]] = []
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        sec_wm = state.get("last_security_watermark") or ""
        if sec_wm:
            cur = conn.execute(
                """
                SELECT timestamp, method, endpoint, status_code, latency_ms
                FROM security_logs
                WHERE timestamp > ?
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (sec_wm, BATCH_LIMIT),
            )
        else:
            cur = conn.execute(
                """
                SELECT timestamp, method, endpoint, status_code, latency_ms
                FROM security_logs
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (INITIAL_SCAN_LIMIT,),
            )
        sec_rows = cur.fetchall()
        if not sec_wm:
            sec_rows = list(reversed(sec_rows))

        for r in sec_rows:
            ts = str(r["timestamp"] or "")
            norm = _normalize_row(
                source="security",
                method=r["method"],
                endpoint=r["endpoint"],
                status=r["status_code"],
                latency_ms=r["latency_ms"],
                time_label=ts,
                sort_key=ts,
                row_key=f"security:{ts}:{r['method']}:{r['endpoint']}:{r['status_code']}",
            )
            if norm:
                rows.append(norm)

        acc_wm = state.get("last_access_watermark") or ""
        if acc_wm:
            try:
                acc_wm_f = float(acc_wm)
            except (TypeError, ValueError):
                acc_wm_f = 0.0
            cur = conn.execute(
                """
                SELECT Timestamp, method, endpoint, status, latency
                FROM request_logs
                WHERE Timestamp > ?
                ORDER BY Timestamp ASC
                LIMIT ?
                """,
                (acc_wm_f, BATCH_LIMIT),
            )
        else:
            cur = conn.execute(
                """
                SELECT Timestamp, method, endpoint, status, latency
                FROM request_logs
                ORDER BY Timestamp DESC
                LIMIT ?
                """,
                (INITIAL_SCAN_LIMIT,),
            )
        acc_rows = cur.fetchall()
        if not acc_wm:
            acc_rows = list(reversed(acc_rows))

        for r in acc_rows:
            ts_raw = r["Timestamp"]
            ts_label = _format_access_time(ts_raw)
            sort_key = str(ts_raw)
            norm = _normalize_row(
                source="access",
                method=r["method"],
                endpoint=r["endpoint"],
                status=r["status"],
                latency_ms=r["latency"],
                time_label=ts_label,
                sort_key=sort_key,
                row_key=f"access:{sort_key}:{r['method']}:{r['endpoint']}:{r['status']}",
            )
            if norm:
                rows.append(norm)
    finally:
        conn.close()

    rows.sort(key=lambda x: x.get("sort_key", ""))
    return rows


def _update_watermarks(state: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    sec_keys = [r["sort_key"] for r in rows if r.get("source") == "security"]
    acc_keys = [r["sort_key"] for r in rows if r.get("source") == "access"]
    if sec_keys:
        state["last_security_watermark"] = max(sec_keys)
    if acc_keys:
        state["last_access_watermark"] = max(acc_keys, key=lambda x: float(x) if x else 0.0)


def _detect_row_anomalies(row: dict[str, Any]) -> list[str]:
    types: list[str] = []
    status = int(row.get("status", 0))
    latency = float(row.get("latency_ms", 0))

    if status >= 500:
        types.append("server_error")
    if latency >= 900:
        types.append("high_latency")
    if status in (401, 403):
        types.append("auth_anomaly")
    if status == 429:
        types.append("rate_limit")
    return types


def _detect_error_spike(rows: list[dict[str, Any]]) -> bool:
    if len(rows) < RECENT_WINDOW:
        return False
    window = rows[-RECENT_WINDOW:]
    errors = sum(1 for r in window if int(r.get("status", 0)) >= 400)
    return errors >= ERROR_SPIKE_THRESHOLD


def _fingerprint(anomaly_type: str, row: dict[str, Any]) -> str:
    if anomaly_type == "error_spike":
        return f"error_spike:{row.get('sort_key', '')}"
    return (
        f"{anomaly_type}:{row.get('source')}:{row.get('method')}:"
        f"{row.get('endpoint')}:{row.get('status')}:{row.get('sort_key')}"
    )


def _should_skip_fingerprint(state: dict[str, Any], fp: str) -> bool:
    seen: list[str] = state.get("seen_fingerprints") or []
    return fp in seen


def _remember_fingerprint(state: dict[str, Any], fp: str) -> None:
    seen: list[str] = list(state.get("seen_fingerprints") or [])
    if fp in seen:
        return
    seen.append(fp)
    if len(seen) > MAX_FINGERPRINTS:
        seen = seen[-MAX_FINGERPRINTS:]
    state["seen_fingerprints"] = seen


def _has_recent_active_alarm(
    alarms: list[dict[str, Any]],
    anomaly_type: str,
    endpoint: str,
) -> bool:
    now = time.time()
    for alarm in alarms:
        if (
            not alarm.get("acknowledged")
            and alarm.get("type") == anomaly_type
            and alarm.get("endpoint") == endpoint
            and (now - float(alarm.get("created_at", 0))) < 25 * 60
        ):
            return True
    return False


def _create_alarm_record(
    anomaly_type: str,
    row: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": _new_id(),
        "created_at": time.time(),
        "time": row.get("time") or _now_iso(),
        "severity": _severity_for_type(anomaly_type),
        "type": anomaly_type,
        "message": _alarm_message(anomaly_type, row),
        "event_id": row.get("row_key"),
        "method": row.get("method"),
        "endpoint": row.get("endpoint"),
        "status": row.get("status"),
        "latency_ms": row.get("latency_ms"),
        "source": row.get("source"),
        "acknowledged": False,
        "origin": "cron_job",
    }


def _notify_alarm_email(alarm: dict[str, Any]) -> None:
    try:
        from app.services.alert_email_service import send_major_alarm_email

        threading.Thread(
            target=send_major_alarm_email,
            args=(alarm,),
            name="cron-alarm-mail",
            daemon=True,
        ).start()
    except Exception:
        pass


def run_alarm_job(*, manual: bool = False) -> dict[str, Any]:
    """Single cron tick: scan logs, create alarms, update job state."""
    global _job_running

    if not is_job_enabled() and not manual:
        return get_job_status()

    with _lock:
        if _job_running:
            busy = True
        else:
            busy = False
            _job_running = True

    if busy:
        return get_job_status()

    started = time.time()
    created = 0
    rows_scanned = 0
    error: str | None = None

    try:
        with _lock:
            state = _load_job_state_unlocked()
            alarms = _load_alarms_unlocked()

        rows = _fetch_log_rows(state)
        rows_scanned = len(rows)

        new_alarms: list[dict[str, Any]] = []

        for row in rows:
            for atype in _detect_row_anomalies(row):
                fp = _fingerprint(atype, row)
                if _should_skip_fingerprint(state, fp):
                    continue
                if _has_recent_active_alarm(alarms, atype, row.get("endpoint", "")):
                    _remember_fingerprint(state, fp)
                    continue

                alarm = _create_alarm_record(atype, row)
                new_alarms.append(alarm)
                _remember_fingerprint(state, fp)

        if rows and _detect_error_spike(rows):
            spike_row = rows[-1]
            fp = _fingerprint("error_spike", spike_row)
            if (
                not _should_skip_fingerprint(state, fp)
                and not _has_recent_active_alarm(alarms, "error_spike", spike_row.get("endpoint", ""))
            ):
                alarm = _create_alarm_record("error_spike", spike_row)
                new_alarms.append(alarm)
                _remember_fingerprint(state, fp)

        if new_alarms:
            alarms = new_alarms + alarms
            created = len(new_alarms)
            for alarm in new_alarms:
                _notify_alarm_email(alarm)

        _update_watermarks(state, rows)

        elapsed_ms = int((time.time() - started) * 1000)
        interval = get_scan_interval_seconds()
        state.update({
            "last_run_at": started,
            "next_run_at": started + interval,
            "last_duration_ms": elapsed_ms,
            "rows_scanned": rows_scanned,
            "alarms_created_last_run": created,
            "last_error": None,
            "run_count": int(state.get("run_count", 0)) + 1,
        })

        with _lock:
            _save_alarms_unlocked(alarms)
            _save_job_state_unlocked(state)

    except Exception as exc:
        error = str(exc)
        with _lock:
            state = _load_job_state_unlocked()
            interval = get_scan_interval_seconds()
            state.update({
                "last_run_at": started,
                "next_run_at": started + interval,
                "last_duration_ms": int((time.time() - started) * 1000),
                "rows_scanned": rows_scanned,
                "alarms_created_last_run": created,
                "last_error": error,
                "run_count": int(state.get("run_count", 0)) + 1,
            })
            _save_job_state_unlocked(state)
    finally:
        with _lock:
            _job_running = False

    status = get_job_status()
    status["alarms_created"] = created
    status["manual"] = manual
    if error:
        status["error"] = error
    return status


def get_job_status() -> dict[str, Any]:
    with _lock:
        state = _load_job_state_unlocked()
        alarms = _load_alarms_unlocked()

    interval = get_scan_interval_seconds()
    last_run = float(state.get("last_run_at") or 0)
    next_run = float(state.get("next_run_at") or 0)
    now = time.time()

    if not last_run and is_job_enabled():
        next_run = now + interval

    return {
        "enabled": is_job_enabled(),
        "running": _job_running,
        "scan_interval_seconds": interval,
        "last_run_at": last_run,
        "last_run_time": _now_iso() if last_run else None,
        "last_run_label": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_run)) if last_run else "-",
        "next_run_at": next_run,
        "next_run_label": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(next_run)) if next_run else "-",
        "seconds_until_next": max(0, int(next_run - now)) if next_run else interval,
        "last_duration_ms": int(state.get("last_duration_ms") or 0),
        "rows_scanned": int(state.get("rows_scanned") or 0),
        "alarms_created_last_run": int(state.get("alarms_created_last_run") or 0),
        "run_count": int(state.get("run_count") or 0),
        "last_error": state.get("last_error"),
        "active_alarms": sum(1 for a in alarms if not a.get("acknowledged")),
        "total_alarms": len(alarms),
    }


def list_alarms(include_acknowledged: bool = False) -> list[dict[str, Any]]:
    with _lock:
        alarms = _load_alarms_unlocked()
    if include_acknowledged:
        return alarms
    return [a for a in alarms if not a.get("acknowledged")]


def acknowledge_alarms(alarm_ids: list[str]) -> int:
    if not alarm_ids:
        return 0

    id_set = set(alarm_ids)
    count = 0
    with _lock:
        alarms = _load_alarms_unlocked()
        for alarm in alarms:
            if alarm["id"] in id_set and not alarm.get("acknowledged"):
                alarm["acknowledged"] = True
                count += 1
        if count:
            _save_alarms_unlocked(alarms)
    return count


def get_alarm_stats() -> dict[str, Any]:
    with _lock:
        alarms = _load_alarms_unlocked()
    return {
        "active_alarms": sum(1 for a in alarms if not a.get("acknowledged")),
        "total_alarms": len(alarms),
    }


def _job_loop(app) -> None:
    while True:
        interval = get_scan_interval_seconds()
        try:
            with app.app_context():
                if is_job_enabled():
                    run_alarm_job()
        except Exception:
            pass
        time.sleep(interval)


def ensure_job_running(app) -> None:
    global _job_thread_started
    with _lock:
        if _job_thread_started:
            return
        _job_thread_started = True

    threading.Thread(
        target=_job_loop,
        args=(app,),
        name="alarm-cron-job",
        daemon=True,
    ).start()
