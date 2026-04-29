from flask import Blueprint, jsonify, session

from app.services.dashboard_service import get_dashboard_data
from app.api.routes.auth import failed_logins, successful_logins


metrics_bp = Blueprint("metrics", __name__)


@metrics_bp.route("/metrics")
def metrics():
    if "user" not in session:
        return jsonify({"error": "unauthorized"}), 401

    data = get_dashboard_data(failed_logins, successful_logins)
    return jsonify(data)