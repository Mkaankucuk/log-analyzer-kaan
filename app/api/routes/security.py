import json
from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from app.services.security_service import get_security_summary, get_security_chart_data

security_bp = Blueprint("security", __name__)


@security_bp.route("/dashboard/security-logs")
def security_logs():
    if "user" not in session:
        return redirect(url_for("auth.home"))

    interval = request.args.get("interval", "hour")

    summary = get_security_summary()
    charts = get_security_chart_data(interval=interval)

    return render_template(
        "pages/security_logs.html",
        user=session["user"],
        active_page="security",
        summary=summary,
        selected_interval=interval,
        status_chart=json.dumps(charts["status_chart"]),
        error_type_chart=json.dumps(charts["error_type_chart"]),
        latency_chart=json.dumps(charts["latency_chart"])
    )


@security_bp.route("/api/security-chart-data")
def security_chart_data():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401

    interval = request.args.get("interval", "hour")
    charts = get_security_chart_data(interval=interval)

    return jsonify(charts)