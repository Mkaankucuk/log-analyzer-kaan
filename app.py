from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey123"

# Sabit admin
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"

# Loglar
logs = []
successful_logins = []
failed_logins = []


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session["user"] = username

        successful_logins.append({
            "username": username,
            "message": "Başarılı login",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        return redirect(url_for("dashboard"))

    else:
        failed_logins.append({
            "username": username,
            "message": "Hatalı login",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        return render_template("index.html", error="Kullanıcı adı veya şifre hatalı.")


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("home"))

    user = session.get("user")

    total_logs = len(logs)
    error_logs = len([log for log in logs if log.get("type") == "ERROR"])
    warning_logs = len([log for log in logs if log.get("type") == "WARNING"])

    failed_login_count = len(failed_logins)
    successful_login_count = len(successful_logins)

    total_login_attempts = failed_login_count + successful_login_count

    if total_login_attempts > 0:
        failed_login_rate = (failed_login_count / total_login_attempts) * 100
    else:
        failed_login_rate = 0

    return render_template(
        "dashboard.html",
        user=user,
        total_logs=total_logs,
        error_logs=error_logs,
        warning_logs=warning_logs,
        failed_login_count=failed_login_count,
        failed_login_rate=round(failed_login_rate, 2),
        failed_logins=failed_logins,
        successful_logins=successful_logins
    )


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)