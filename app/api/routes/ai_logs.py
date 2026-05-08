from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from app.services.ai_log_service import run_ai_log_analysis
from app.services.access_logs_service import get_access_filter_options


ai_logs_bp = Blueprint("ai_logs", __name__)


@ai_logs_bp.route("/dashboard/ai-logs")
def ai_logs_page():
    if "user" not in session:
        return redirect(url_for("auth.home"))

    access_filter_options = get_access_filter_options()

    return render_template(
        "pages/ai_logs.html",
        user=session["user"],
        active_page="ai_logs",
        filter_methods=access_filter_options["methods"],
        filter_endpoints=access_filter_options["endpoints"]
    )


@ai_logs_bp.route("/api/ai-log-analysis", methods=["POST"])
def ai_log_analysis():
    if "user" not in session:
        return jsonify({"ok": False, "message": "unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    source = payload.get("source", "access")
    limit = int(payload.get("limit", 100))
    limit = max(100, min(limit, 3000))
    methods = payload.get("methods") or []
    endpoint = payload.get("endpoint")
    status_group = payload.get("status_group")
    response_mode = payload.get("response_mode", "tr")

    result = run_ai_log_analysis(
        limit=limit,
        methods=methods,
        endpoint=endpoint,
        status_group=status_group,
        source=source,
        response_mode=response_mode
    )
    status_code = 200 if result["ok"] else 400
    return jsonify(result), status_code
