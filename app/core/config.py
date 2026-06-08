from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parents[2]


class Config:
    SECRET_KEY = "supersecretkey123"
    BASE_DIR = BASE_DIR
    DB_PATH = BASE_DIR / "logs.db"
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
    OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))
    OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "15m")

    TEMP_UPLOAD_DIR = BASE_DIR / "tmp" / "uploads"
    TEMP_UPLOAD_MAX_BYTES = 15 * 1024 * 1024
    TEMP_UPLOAD_MAX_AGE_SECONDS = int(os.getenv("TEMP_UPLOAD_MAX_AGE_SECONDS", "3600"))
    MAX_CONTENT_LENGTH = TEMP_UPLOAD_MAX_BYTES

    MAIL_ENABLED = os.getenv("MAIL_ENABLED", "0").strip().lower() in ("1", "true", "yes")
    MAIL_SMTP_HOST = os.getenv("MAIL_SMTP_HOST", "")
    MAIL_SMTP_PORT = int(os.getenv("MAIL_SMTP_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "1").strip().lower() in ("1", "true", "yes")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_FROM = os.getenv("MAIL_FROM", MAIL_USERNAME)
    MAIL_TO = os.getenv("MAIL_TO", "")
    ALERT_EMAIL_COOLDOWN_SECONDS = int(os.getenv("ALERT_EMAIL_COOLDOWN_SECONDS", "300"))
