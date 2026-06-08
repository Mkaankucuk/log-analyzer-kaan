import time
import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename


file_upload_bp = Blueprint("file_upload", __name__)

# Oturumda geçici yüklenen dosya adı (AI analizi ve dosya önizleme sayfası ortak kullanır).
SESSION_TEMP_NAME_KEY = "file_upload_temp_name"


def _upload_dir() -> Path:
    return Path(current_app.config["TEMP_UPLOAD_DIR"])


def _cleanup_old_uploads(upload_dir: Path, max_age_seconds: int) -> None:
    if not upload_dir.is_dir():
        return
    cutoff = time.time() - max_age_seconds
    for path in upload_dir.iterdir():
        if path.is_file():
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
            except OSError:
                pass


def _unlink_session_temp(upload_dir: Path, basename: str | None) -> None:
    if not basename or "/" in basename or "\\" in basename or basename.startswith("."):
        return
    path = (upload_dir / basename).resolve()
    try:
        root = upload_dir.resolve()
        if path.parent != root or not path.is_file():
            return
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _display_name_from_stored(stored_name: str) -> str:
    if "_" in stored_name:
        prefix, rest = stored_name.split("_", 1)
        if len(prefix) == 32 and rest and all(c in "0123456789abcdef" for c in prefix):
            return rest
    return stored_name


def _clear_session_temp_for_page_load() -> None:
    """Sayfa her yüklendiğinde (yenileme dahil) geçici dosyayı sil; kalıcı sayfa durumu olmasın."""
    upload_dir = _upload_dir()
    prev = session.pop(SESSION_TEMP_NAME_KEY, None)
    if prev is None:
        return
    if upload_dir.is_dir():
        _unlink_session_temp(upload_dir, prev)
    session.modified = True


@file_upload_bp.route("/dashboard/file-upload")
def file_upload_page():
    if "user" not in session:
        return redirect(url_for("auth.home"))

    _clear_session_temp_for_page_load()

    return render_template(
        "pages/file_upload.html",
        user=session["user"],
        active_page="file_upload",
    )


@file_upload_bp.route("/dashboard/file-upload/temp", methods=["GET"])
def get_temp_upload():
    if "user" not in session:
        return jsonify(ok=False, message="unauthorized"), 401

    stored_name = session.get(SESSION_TEMP_NAME_KEY)
    if not stored_name:
        return jsonify(ok=True, has_file=False)

    upload_dir = _upload_dir()
    path = (upload_dir / stored_name).resolve()
    try:
        root = upload_dir.resolve()
        if path.parent != root or not path.is_file():
            session.pop(SESSION_TEMP_NAME_KEY, None)
            session.modified = True
            return jsonify(ok=True, has_file=False)
        size = path.stat().st_size
    except OSError:
        session.pop(SESSION_TEMP_NAME_KEY, None)
        session.modified = True
        return jsonify(ok=True, has_file=False)

    return jsonify(
        ok=True,
        has_file=True,
        stored_name=stored_name,
        display_name=_display_name_from_stored(stored_name),
        size_bytes=size,
    )


@file_upload_bp.route("/dashboard/file-upload/temp", methods=["POST"])
def save_temp_upload():
    if "user" not in session:
        return jsonify(ok=False, message="unauthorized"), 401

    upload_dir = _upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)

    _cleanup_old_uploads(
        upload_dir,
        int(current_app.config["TEMP_UPLOAD_MAX_AGE_SECONDS"]),
    )

    prev = session.pop(SESSION_TEMP_NAME_KEY, None)
    _unlink_session_temp(upload_dir, prev)

    if "file" not in request.files:
        return jsonify(ok=False, message="no_file"), 400

    uploaded = request.files["file"]
    if not uploaded or not uploaded.filename:
        return jsonify(ok=False, message="no_file"), 400

    max_bytes = int(current_app.config["TEMP_UPLOAD_MAX_BYTES"])
    safe_orig = secure_filename(uploaded.filename) or "upload"
    stored_name = f"{uuid.uuid4().hex}_{safe_orig}"
    dest = upload_dir / stored_name

    uploaded.save(dest)

    try:
        size = dest.stat().st_size
    except OSError:
        dest.unlink(missing_ok=True)
        return jsonify(ok=False, message="save_failed"), 500

    if size > max_bytes:
        dest.unlink(missing_ok=True)
        return jsonify(ok=False, message="too_large"), 400

    session[SESSION_TEMP_NAME_KEY] = stored_name
    session.modified = True

    return jsonify(
        ok=True,
        stored_name=stored_name,
        size_bytes=size,
    )


@file_upload_bp.route("/dashboard/file-upload/temp/clear", methods=["POST"])
def clear_temp_upload():
    if "user" not in session:
        return jsonify(ok=False, message="unauthorized"), 401

    upload_dir = _upload_dir()
    prev = session.pop(SESSION_TEMP_NAME_KEY, None)
    _unlink_session_temp(upload_dir, prev)
    session.modified = True

    return jsonify(ok=True)
