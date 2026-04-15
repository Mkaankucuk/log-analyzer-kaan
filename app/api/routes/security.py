import json
from flask import Blueprint, render_template, session, redirect, url_for

from app.services.security_service import get_security_summary, get_security_chart_data

security_bp = Blueprint("security", __name__)


@security_bp.route("/dashboard/security-logs")
def security_logs():
    if "user" not in session:
        return redirect(url_for("auth.home"))

    summary = get_security_summary()
    charts = get_security_chart_data()

    return render_template(
        "pages/security_logs.html",
        user=session["user"],
        active_page="security",
        summary=summary,
        status_chart=json.dumps(charts["status_chart"]),
        error_type_chart=json.dumps(charts["error_type_chart"]),
        latency_chart=json.dumps(charts["latency_chart"])
    )