"""Runtime mail alert settings (admin panel); SMTP secrets stay in .env."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

_lock = threading.Lock()

_DEFAULTS: dict[str, Any] = {
    "mail_enabled": True,
    "cooldown_seconds": 300,
    "mail_to": "",
    "send_major_only": True,
    "include_recommendations": True,
    "include_buffer_stats": True,
    "job_enabled": True,
    "scan_interval_seconds": 300,
}


def _base_dir() -> Path:
    try:
        from flask import current_app

        return Path(current_app.config.get("BASE_DIR", Path(__file__).resolve().parents[2]))
    except RuntimeError:
        return Path(__file__).resolve().parents[2]


def _settings_path() -> Path:
    data_dir = _base_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "mail_settings.json"


def _coerce_settings(raw: dict[str, Any]) -> dict[str, Any]:
    out = dict(_DEFAULTS)
    if "mail_enabled" in raw:
        out["mail_enabled"] = bool(raw["mail_enabled"])
    if "send_major_only" in raw:
        out["send_major_only"] = bool(raw["send_major_only"])
    if "include_recommendations" in raw:
        out["include_recommendations"] = bool(raw["include_recommendations"])
    if "include_buffer_stats" in raw:
        out["include_buffer_stats"] = bool(raw["include_buffer_stats"])
    if "job_enabled" in raw:
        out["job_enabled"] = bool(raw["job_enabled"])
    try:
        cd = int(raw.get("cooldown_seconds", out["cooldown_seconds"]))
        out["cooldown_seconds"] = max(60, min(cd, 3600))
    except (TypeError, ValueError):
        pass
    try:
        scan = int(raw.get("scan_interval_seconds", out["scan_interval_seconds"]))
        out["scan_interval_seconds"] = max(60, min(scan, 3600))
    except (TypeError, ValueError):
        pass
    mail_to = str(raw.get("mail_to") or "").strip()
    if mail_to:
        out["mail_to"] = mail_to
    elif os.getenv("MAIL_TO", "").strip():
        out["mail_to"] = os.getenv("MAIL_TO", "").strip()
    return out


def load_mail_settings() -> dict[str, Any]:
    path = _settings_path()
    with _lock:
        if not path.is_file():
            return _coerce_settings({})
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _coerce_settings({})
        if not isinstance(raw, dict):
            return _coerce_settings({})
        return _coerce_settings(raw)


def save_mail_settings(updates: dict[str, Any]) -> dict[str, Any]:
    current = load_mail_settings()
    merged = {**current, **updates}
    settings = _coerce_settings(merged)
    path = _settings_path()
    with _lock:
        path.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
    return settings


def get_effective_mail_to() -> list[str]:
    settings = load_mail_settings()
    raw = settings.get("mail_to") or os.getenv("MAIL_TO", "")
    return [a.strip() for a in str(raw).split(",") if a.strip()]


def is_mail_alerts_enabled() -> bool:
    settings = load_mail_settings()
    if not settings.get("mail_enabled", True):
        return False
    return os.getenv("MAIL_ENABLED", "0").strip().lower() in ("1", "true", "yes")


def get_cooldown_seconds() -> int:
    return int(load_mail_settings().get("cooldown_seconds", 300))
