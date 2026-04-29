from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, session
from app.core.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, get_text

from app.utils.auth_utils import is_valid_admin


auth_bp = Blueprint("auth", __name__)

successful_logins = []
failed_logins = []


@auth_bp.route("/")
def home():
    return render_template("pages/index.html")


@auth_bp.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")

    if is_valid_admin(username, password):
        session["user"] = username

        successful_logins.append({
            "username": username,
            "message": "Basarili login",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        return redirect(url_for("system.system_logs"))

    failed_logins.append({
        "username": username,
        "message": "Hatali login",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    return render_template(
        "pages/index.html",
        error=get_text("invalid_login")
    )


@auth_bp.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("auth.home"))


@auth_bp.route("/set-language/<lang>", methods=["POST"])
def set_language(lang):
    if lang in SUPPORTED_LANGUAGES:
        session["lang"] = lang
    elif "lang" not in session:
        session["lang"] = DEFAULT_LANGUAGE

    next_url = request.form.get("next")
    if next_url:
        return redirect(next_url)
    return redirect(url_for("auth.home"))