"""Alert mail: SMTP when configured, otherwise in-app preview outbox."""

from __future__ import annotations

import os
import smtplib
import threading
import time
import uuid
from collections import deque
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from app.services.mail_settings_service import (
    get_cooldown_seconds,
    get_effective_mail_to,
    is_mail_alerts_enabled,
    load_mail_settings,
)

_send_lock = threading.Lock()
_last_sent_at: dict[str, float] = {}
_last_smtp_error: str | None = None
_mail_outbox: deque[dict[str, Any]] = deque(maxlen=40)
MAJOR_ANOMALY_TYPES = frozenset({"server_error", "error_spike"})

_TYPE_LABELS = {
    "server_error": "Sunucu hatası (5xx)",
    "error_spike": "Hata artışı",
    "high_latency": "Yüksek gecikme",
    "auth_anomaly": "Kimlik doğrulama anomalisi",
    "rate_limit": "Oran sınırı (429)",
}

_RECOMMENDATIONS = {
    "server_error": [
        "İlgili servis loglarını ve son deploy değişikliklerini kontrol edin.",
        "Hata oranı artıyorsa trafiği kademeli azaltın veya yedek instance açın.",
        "5xx yanıt veren uç noktada sağlık kontrolü ve timeout ayarlarını gözden geçirin.",
    ],
    "error_spike": [
        "Son dakikalardaki 4xx/5xx dağılımını canlı izleme grafiğinden inceleyin.",
        "Tek bir uç noktada yoğunlaşıyorsa WAF veya rate limit kurallarını kontrol edin.",
        "Geçici trafik artışı mı kalıcı hata mı ayırt etmek için 5–10 dk izleyin.",
    ],
    "high_latency": [
        "Yavaş uç nokta için veritabanı sorguları ve dış API çağrılarını profil edin.",
        "Gecikme eşiğini aşan isteklerde timeout ve retry politikalarını gözden geçirin.",
    ],
    "auth_anomaly": [
        "401/403 artışında brute-force veya token süresi sorunlarını kontrol edin.",
        "Şüpheli IP'ler için erişim kısıtlaması veya MFA zorunluluğu değerlendirin.",
    ],
    "rate_limit": [
        "429 yanıtlarında istemci yeniden deneme (backoff) politikalarını doğrulayın.",
        "Limit eşiklerinin mevcut trafik için yeterli olup olmadığını kontrol edin.",
    ],
}


def _smtp_ready() -> bool:
    if not is_mail_alerts_enabled():
        return False
    if not _normalize_password(os.getenv("MAIL_PASSWORD", "")):
        return False
    if not os.getenv("MAIL_SMTP_HOST", "").strip():
        return False
    if not get_effective_mail_to():
        return False
    if not os.getenv("MAIL_FROM", os.getenv("MAIL_USERNAME", "")).strip():
        return False
    return True


def _cooldown_seconds() -> int:
    return get_cooldown_seconds()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def _should_send(kind: str) -> bool:
    now = time.time()
    with _send_lock:
        last = _last_sent_at.get(kind, 0.0)
        if now - last < _cooldown_seconds():
            return False
        _last_sent_at[kind] = now
    return True


def is_major_alarm(alarm: dict[str, Any]) -> bool:
    if alarm.get("severity") == "critical":
        return True
    return alarm.get("type") in MAJOR_ANOMALY_TYPES


def should_send_alarm_email(alarm: dict[str, Any]) -> bool:
    settings = load_mail_settings()
    if settings.get("send_major_only", True):
        return is_major_alarm(alarm)
    return bool(alarm.get("type"))


def get_mail_outbox(limit: int = 20) -> list[dict[str, Any]]:
    with _send_lock:
        return list(_mail_outbox)[:limit]


def get_mail_status() -> dict[str, Any]:
    settings = load_mail_settings()
    ready = _smtp_ready()
    with _send_lock:
        last_error = _last_smtp_error
    return {
        "enabled": is_mail_alerts_enabled(),
        "smtp_ready": ready,
        "has_password": bool(os.getenv("MAIL_PASSWORD", "").strip()),
        "recipient": ", ".join(get_effective_mail_to()),
        "last_error": last_error,
        "cooldown_seconds": settings.get("cooldown_seconds", 300),
        "send_major_only": settings.get("send_major_only", True),
    }


def _normalize_password(raw: str) -> str:
    return raw.replace(" ", "").strip()


def _buffer_stats_block() -> str:
    settings = load_mail_settings()
    if not settings.get("include_buffer_stats", True):
        return ""
    try:
        from app.services.alarm_job_service import get_job_status
        from app.services.live_monitor_service import get_buffer_stats

        s = get_buffer_stats()
        job = get_job_status()
        return (
            "\n--- Sistem özeti ---\n"
            f"Canlı tampon olay: {s.get('buffer_size', 0)}\n"
            f"Aktif alarm (cron): {s.get('active_alarms', 0)}\n"
            f"Son anomaliler (canlı): {s.get('recent_anomalies', 0)}\n"
            f"Cron son tarama: {job.get('last_run_label', '-')}\n"
            f"Cron aralığı: {job.get('scan_interval_seconds', '-')} sn\n"
        )
    except Exception:
        return ""


def _build_detailed_alarm_body(alarm: dict[str, Any]) -> str:
    settings = load_mail_settings()
    atype = alarm.get("type", "unknown")
    severity = alarm.get("severity", "warning")
    type_label = _TYPE_LABELS.get(atype, atype)
    cooldown_min = max(1, _cooldown_seconds() // 60)

    lines = [
        "LOG ANALYZER — ANOMALİ BİLDİRİMİ",
        "=" * 40,
        "",
        "ÖZET",
        f"  Önem derecesi : {severity.upper()}",
        f"  Anomali türü  : {type_label} ({atype})",
        f"  Alarm zamanı  : {alarm.get('time', '-')}",
        f"  Alarm kimliği : {alarm.get('id', '-')}",
        "",
        "OLAY DETAYI",
        f"  Açıklama      : {alarm.get('message', '-')}",
        f"  İstek yöntemi : {alarm.get('method', '-')}",
        f"  Uç nokta      : {alarm.get('endpoint', '-')}",
        f"  Durum kodu    : {alarm.get('status', '-')}",
        f"  Gecikme       : {alarm.get('latency_ms', '-')} ms",
        f"  İlişkili olay : {alarm.get('event_id', '-')}",
        "",
        "EŞİKLER",
        "  Kritik sayılan: HTTP 5xx, hata artışı (error_spike)",
        "  Uyarı sayılan : yüksek gecikme (≥900 ms), 401/403, 429",
        "",
        f"GÖNDERİM POLİTİKASI",
        f"  Aynı tür için en az {cooldown_min} dakika arayla mail gönderilir.",
        f"  Alıcı(lar)    : {', '.join(get_effective_mail_to()) or '-'}",
    ]

    if settings.get("include_recommendations", True):
        recs = _RECOMMENDATIONS.get(atype, [
            "Canlı izleme ve alarm merkezinden durumu doğrulayın.",
            "Gerekirse ilgili uç noktayı geçici olarak devre dışı bırakın.",
        ])
        lines.append("")
        lines.append("ÖNERİLEN AKSİYONLAR")
        for i, rec in enumerate(recs, 1):
            lines.append(f"  {i}. {rec}")

    lines.append(_buffer_stats_block())
    lines.append("")
    lines.append("---")
    lines.append("Log Analyzer — otomatik anomali bildirimi")
    if not _smtp_ready():
        lines.append("(SMTP yapılandırılmadı; bu metin yalnızca panel önizlemesidir.)")

    return "\n".join(lines)


def _update_outbox_entry(entry_id: str, *, sent: bool, error: str | None = None) -> None:
    with _send_lock:
        for item in _mail_outbox:
            if item.get("id") == entry_id:
                item["sent_smtp"] = sent
                item["smtp_error"] = error
                item["preview_only"] = not sent
                break


def _smtp_send(
    subject: str,
    body: str,
    *,
    kind: str,
    entry_id: str | None = None,
    respect_cooldown: bool = True,
) -> bool:
    global _last_smtp_error

    if not _smtp_ready():
        _last_smtp_error = "SMTP yapılandırması eksik"
        return False

    if respect_cooldown and not _should_send(kind):
        _last_smtp_error = "Bekleme süresi (cooldown) aktif; mail atlanıldı"
        return False

    recipients = get_effective_mail_to()
    host = os.getenv("MAIL_SMTP_HOST", "").strip()
    username = os.getenv("MAIL_USERNAME", "").strip()
    password = _normalize_password(os.getenv("MAIL_PASSWORD", ""))
    mail_from = os.getenv("MAIL_FROM", username).strip()

    try:
        port = int(os.getenv("MAIL_SMTP_PORT", "587"))
    except ValueError:
        port = 587
    use_tls = os.getenv("MAIL_USE_TLS", "1").strip().lower() in ("1", "true", "yes")

    msg = MIMEMultipart()
    msg["From"] = mail_from
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()
            server.login(username, password)
            server.sendmail(mail_from, recipients, msg.as_string())
        with _send_lock:
            _last_smtp_error = None
        if entry_id:
            _update_outbox_entry(entry_id, sent=True)
        return True
    except (OSError, smtplib.SMTPException) as exc:
        err = str(exc)
        with _send_lock:
            _last_smtp_error = err
        if entry_id:
            _update_outbox_entry(entry_id, sent=False, error=err)
        return False


def queue_alert_mail(
    subject: str,
    body: str,
    *,
    kind: str = "generic",
    alarm: dict[str, Any] | None = None,
    respect_cooldown: bool = True,
) -> dict[str, Any]:
    entry = {
        "id": uuid.uuid4().hex[:12],
        "time": _now_iso(),
        "subject": subject,
        "body": body,
        "kind": kind,
        "preview_only": not _smtp_ready(),
        "sent_smtp": False,
        "alarm_id": (alarm or {}).get("id"),
    }

    with _send_lock:
        _mail_outbox.appendleft(entry)

    if _smtp_ready():
        entry_id = entry["id"]

        def _send_async() -> None:
            _smtp_send(
                subject,
                body,
                kind=kind,
                entry_id=entry_id,
                respect_cooldown=respect_cooldown,
            )

        threading.Thread(target=_send_async, name="alert-smtp", daemon=True).start()

    return entry


def send_major_alarm_email(alarm: dict[str, Any]) -> dict[str, Any] | None:
    if not should_send_alarm_email(alarm):
        return None

    kind = f"major_alarm_{alarm.get('type', 'x')}"
    severity = alarm.get("severity", "critical")
    atype = alarm.get("type", "anomaly")
    subject = (
        f"[Log Analyzer] ANOMALİ ({severity.upper()}) — "
        f"{_TYPE_LABELS.get(atype, atype)} | "
        f"{alarm.get('method', '')} {alarm.get('endpoint', '')}"
    )
    body = _build_detailed_alarm_body(alarm)
    return queue_alert_mail(subject, body, kind=kind, alarm=alarm)


def send_test_email() -> dict[str, Any]:
    body = (
        "LOG ANALYZER — SMTP TEST\n"
        "=" * 40 + "\n\n"
        "Bu mesaj mail yönetim panelinden gönderilen bir testtir.\n"
        f"Alıcı: {', '.join(get_effective_mail_to()) or '-'}\n"
        f"Cooldown: {_cooldown_seconds()} saniye\n"
        f"Zaman: {_now_iso()}\n"
    )
    return queue_alert_mail(
        "[Log Analyzer] SMTP test",
        body,
        kind="smtp_test_admin",
        respect_cooldown=False,
    )
