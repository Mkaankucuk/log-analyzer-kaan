from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify

from app.services.dashboard_service import get_dashboard_data
from app.services.access_logs_service import get_chart_data, get_access_filter_options

main = Blueprint("main", __name__)

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"

successful_logins = []
failed_logins = []


@main.route("/")
def home():
    return render_template("pages/index.html")


@main.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session["user"] = username

        successful_logins.append({
            "username": username,
            "message": "Basarili login",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        return redirect(url_for("main.system_logs"))

    failed_logins.append({
        "username": username,
        "message": "Hatali login",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    return render_template("pages/index.html", error="Kullanici adi veya sifre hatali.")


@main.route("/dashboard/system-logs")
def system_logs():
    if "user" not in session:
        return redirect(url_for("main.home"))

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


@main.route("/dashboard/access-logs")
def access_logs():
    if "user" not in session:
        return redirect(url_for("main.home"))

    chart_data = get_chart_data()
    filter_options = get_access_filter_options()

    return render_template(
        "pages/access_logs.html",
        user=session["user"],
        active_page="access",
        method_chart_data=chart_data["method_chart_data"],
        request_error_chart=chart_data["request_error_chart"],
        latency_chart=chart_data["latency_chart"],
        filter_methods=filter_options["methods"],
        filter_endpoints=filter_options["endpoints"],
        filter_status_codes=filter_options["status_codes"]
    )


@main.route("/dashboard/trend-logs")
def trend_logs():
    if "user" not in session:
        return redirect(url_for("main.home"))

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


@main.route("/api/access-logs-data")
def access_logs_data():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401

    methods = request.args.getlist("method")
    status_group = request.args.get("status_group")
    status_code = request.args.get("status_code")
    endpoint = request.args.get("endpoint")
    interval = request.args.get("interval", "hour")

    chart_data = get_chart_data(
        methods=methods if methods else None,
        status_group=status_group,
        status_code=status_code,
        endpoint=endpoint,
        interval=interval
    )

    return jsonify(chart_data)


@main.route("/metrics")
def metrics():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401

    data = get_dashboard_data(failed_logins, successful_logins)
    return jsonify(data)


@main.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("main.home"))
