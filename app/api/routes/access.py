from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify

from app.services.access_logs_service import get_chart_data, get_access_filter_options


access_bp = Blueprint("access", __name__)


@access_bp.route("/dashboard/access-logs")
def access_logs():
    if "user" not in session:
        return redirect(url_for("auth.home"))

    filter_options = get_access_filter_options()
    empty_charts = {
        "method_chart_data": {},
        "request_error_chart": {"x": [], "total_requests": [], "error_count": []},
        "latency_chart": {"x": [], "avg_latency": []},
    }

    return render_template(
        "pages/access_logs.html",
        user=session["user"],
        active_page="access",
        method_chart_data=empty_charts["method_chart_data"],
        request_error_chart=empty_charts["request_error_chart"],
        latency_chart=empty_charts["latency_chart"],
        filter_methods=filter_options["methods"],
        filter_endpoints=filter_options["endpoints"],
        filter_status_codes=filter_options["status_codes"]
    )


@access_bp.route("/api/access-logs-data")
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