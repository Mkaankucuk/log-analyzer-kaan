from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from app.services.alert_email_service import get_mail_status, send_test_email
from app.services.mail_settings_service import load_mail_settings, save_mail_settings


mail_admin_bp = Blueprint("mail_admin", __name__)


@mail_admin_bp.route("/dashboard/mail-admin")
def mail_admin_page():
    if "user" not in session:
        return redirect(url_for("auth.home"))

    settings = load_mail_settings()
    status = get_mail_status()

    return render_template(
        "pages/mail_admin.html",
        user=session["user"],
        active_page="mail_admin",
        mail_settings=settings,
        mail_status=status,
    )


@mail_admin_bp.route("/api/mail-admin/settings", methods=["GET"])
def mail_settings_get():
    if "user" not in session:
        return jsonify(ok=False, message="unauthorized"), 401

    return jsonify(ok=True, settings=load_mail_settings(), status=get_mail_status())


@mail_admin_bp.route("/api/mail-admin/settings", methods=["POST"])
def mail_settings_save():
    if "user" not in session:
        return jsonify(ok=False, message="unauthorized"), 401

    payload = request.get_json(silent=True) or {}
    updates: dict = {}

    if "mail_enabled" in payload:
        updates["mail_enabled"] = bool(payload["mail_enabled"])
    if "send_major_only" in payload:
        updates["send_major_only"] = bool(payload["send_major_only"])
    if "include_recommendations" in payload:
        updates["include_recommendations"] = bool(payload["include_recommendations"])
    if "include_buffer_stats" in payload:
        updates["include_buffer_stats"] = bool(payload["include_buffer_stats"])
    if "cooldown_seconds" in payload:
        try:
            updates["cooldown_seconds"] = int(payload["cooldown_seconds"])
        except (TypeError, ValueError):
            pass
    if "mail_to" in payload:
        updates["mail_to"] = str(payload["mail_to"] or "").strip()
    if "job_enabled" in payload:
        updates["job_enabled"] = bool(payload["job_enabled"])
    if "scan_interval_seconds" in payload:
        try:
            updates["scan_interval_seconds"] = int(payload["scan_interval_seconds"])
        except (TypeError, ValueError):
            pass

    settings = save_mail_settings(updates)
    return jsonify(ok=True, settings=settings, status=get_mail_status())


@mail_admin_bp.route("/api/mail-admin/test", methods=["POST"])
def mail_test_send():
    if "user" not in session:
        return jsonify(ok=False, message="unauthorized"), 401

    entry = send_test_email()
    return jsonify(
        ok=True,
        message="test_queued",
        entry=entry,
        status=get_mail_status(),
    )
