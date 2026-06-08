from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from app.services.alert_email_service import get_mail_outbox
from app.services.alarm_job_service import (
    get_job_status,
    list_alarms,
    run_alarm_job,
)
from app.services.live_monitor_service import (
    acknowledge_alarms,
    ensure_generator_running,
    get_snapshot,
)


live_monitor_bp = Blueprint("live_monitor", __name__)


@live_monitor_bp.route("/dashboard/live-monitor")
def live_monitor_page():
    if "user" not in session:
        return redirect(url_for("auth.home"))

    ensure_generator_running()

    return render_template(
        "pages/live_monitor.html",
        user=session["user"],
        active_page="live_monitor",
    )


@live_monitor_bp.route("/dashboard/alarms")
def alarms_page():
    if "user" not in session:
        return redirect(url_for("auth.home"))

    ensure_generator_running()

    return render_template(
        "pages/alarms.html",
        user=session["user"],
        active_page="alarms",
    )


@live_monitor_bp.route("/api/live/snapshot")
def live_snapshot():
    if "user" not in session:
        return jsonify(ok=False, message="unauthorized"), 401

    since_event = request.args.get("since_event_id") or None
    since_alarm = request.args.get("since_alarm_id") or None

    return jsonify(get_snapshot(since_event_id=since_event, since_alarm_id=since_alarm))


@live_monitor_bp.route("/api/live/alarms")
def live_alarms_list():
    if "user" not in session:
        return jsonify(ok=False, message="unauthorized"), 401

    include_ack = request.args.get("include_acknowledged", "0") == "1"
    return jsonify(ok=True, alarms=list_alarms(include_acknowledged=include_ack))


@live_monitor_bp.route("/api/live/mail-outbox")
def live_mail_outbox():
    if "user" not in session:
        return jsonify(ok=False, message="unauthorized"), 401

    return jsonify(ok=True, mails=get_mail_outbox())


@live_monitor_bp.route("/api/live/alarms/ack", methods=["POST"])
def live_alarms_ack():
    if "user" not in session:
        return jsonify(ok=False, message="unauthorized"), 401

    payload = request.get_json(silent=True) or {}
    alarm_ids = payload.get("alarm_ids") or []
    if not isinstance(alarm_ids, list):
        alarm_ids = []

    count = acknowledge_alarms([str(i) for i in alarm_ids])
    return jsonify(ok=True, acknowledged=count)


@live_monitor_bp.route("/api/live/alarm-job")
def live_alarm_job_status():
    if "user" not in session:
        return jsonify(ok=False, message="unauthorized"), 401

    return jsonify(ok=True, job=get_job_status())


@live_monitor_bp.route("/api/live/alarm-job/run", methods=["POST"])
def live_alarm_job_run():
    if "user" not in session:
        return jsonify(ok=False, message="unauthorized"), 401

    result = run_alarm_job(manual=True)
    return jsonify(ok=True, job=result)
