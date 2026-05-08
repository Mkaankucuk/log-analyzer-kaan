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

    app.register_blueprint(auth_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(access_bp)
    app.register_blueprint(trend_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(security_bp)
    app.register_blueprint(ai_logs_bp)

    @app.context_processor
    def inject_i18n():
        return {
            "t": get_text,
            "current_lang": get_locale(),
            "supported_langs": sorted(SUPPORTED_LANGUAGES),
            "js_translations": get_js_translations()
        }

    return app