from flask import Blueprint, render_template, redirect, url_for, session

from app.services.dashboard_service import get_dashboard_data
from app.api.routes.auth import failed_logins, successful_logins


system_bp = Blueprint("system", __name__)


@system_bp.route("/dashboard/system-logs")
def system_logs():
    if "user" not in session:
        return redirect(url_for("auth.home"))

    data = get_dashboard_data(failed_logins, successful_logins)

    return render_template(
        "pages/system_logs.html",
        user=session["user"],
        active_page="system",
        total_logs=data["total_logs"],
        error_logs=data["error_logs"],
        warning_logs=data["warning_logs"],
        cpu_usage=data["cpu_usage"],
        cpu_class=data["cpu_class"],
        memory_usage=data["memory_usage"],
        memory_class=data["memory_class"],
        top_processes=data["top_processes"]
    )