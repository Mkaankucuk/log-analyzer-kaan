from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# Şimdilik sabit admin bilgisi
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "1234"


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return redirect(url_for("dashboard"))
    else:
        return render_template("index.html", error="Kullanıcı adı veya şifre hatalı.")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

if __name__ == "__main__":
    app.run(debug=True)