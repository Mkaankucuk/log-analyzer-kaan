from flask import Blueprint, render_template, redirect, url_for, session

from app.services.dashboard_service import get_dashboard_data
from app.api.routes.auth import failed_logins, successful_logins


trend_bp = Blueprint("trend", __name__)


@trend_bp.route("/dashboard/trend-logs")
def trend_logs():
    if "user" not in session:
        return redirect(url_for("auth.home"))

    data = get_dashboard_data(failed_logins, successful_logins)

    return render_template(
        "pages/trend_logs.html",
        user=session["user"],
        active_page="trend",
        failed_login_count=data["failed_login_count"],
        failed_login_rate=data["failed_login_rate"],
        failed_logins=data["failed_logins"],
        successful_logins=data["successful_logins"]
    )