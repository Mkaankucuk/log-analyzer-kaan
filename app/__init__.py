from app.core.env_loader import load_env

load_env()

from flask import Flask
from app.core import Config
from app.core.i18n import get_locale, get_text, SUPPORTED_LANGUAGES, get_js_translations


def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static"
    )

    app.config.from_object(Config)

    from app.api.routes.auth import auth_bp
    from app.api.routes.system import system_bp
    from app.api.routes.access import access_bp
    from app.api.routes.trend import trend_bp
    from app.api.routes.metrics import metrics_bp
    from app.api.routes.security import security_bp
    from app.api.routes.ai_logs import ai_logs_bp
    from app.api.routes.file_upload import file_upload_bp
    from app.api.routes.live_monitor import live_monitor_bp
    from app.api.routes.mail_admin import mail_admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(access_bp)
    app.register_blueprint(trend_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(security_bp)
    app.register_blueprint(ai_logs_bp)
    app.register_blueprint(file_upload_bp)
    app.register_blueprint(live_monitor_bp)
    app.register_blueprint(mail_admin_bp)

    _warm_caches_in_background(app)
    _warm_ollama_in_background(app)
    _start_alarm_cron_job(app)

    @app.context_processor
    def inject_i18n():
        return {
            "t": get_text,
            "current_lang": get_locale(),
            "supported_langs": sorted(SUPPORTED_LANGUAGES),
            "js_translations": get_js_translations()
        }

    return app


def _warm_caches_in_background(app: Flask) -> None:
    import threading

    def _run() -> None:
        with app.app_context():
            try:
                from app.services.access_logs_service import load_request_logs

                load_request_logs()
            except Exception:
                pass

    threading.Thread(target=_run, name="warm-log-cache", daemon=True).start()


def _warm_ollama_in_background(app: Flask) -> None:
    import threading

    def _run() -> None:
        with app.app_context():
            try:
                from app.services.ai_log_service import warmup_ollama

                warmup_ollama()
            except Exception:
                pass

    threading.Thread(target=_run, name="warm-ollama", daemon=True).start()


def _start_alarm_cron_job(app: Flask) -> None:
    from app.services.alarm_job_service import ensure_job_running

    ensure_job_running(app)