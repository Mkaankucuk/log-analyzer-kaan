"""SMTP test: python scripts/test_smtp.py"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.env_loader import load_env

load_env()

from app import create_app  # noqa: E402
from app.services.alert_email_service import get_mail_status, send_test_email  # noqa: E402


def main() -> int:
    app = create_app()
    with app.app_context():
        status = get_mail_status()
        print("SMTP hazır:", status.get("smtp_ready"))
        print("Alıcı:", status.get("recipient"))

        if not status.get("smtp_ready"):
            print("HATA: .env içinde MAIL_ENABLED=1 ve MAIL_PASSWORD gerekli.")
            return 1

        send_test_email()
        time.sleep(2)
        status = get_mail_status()
        if status.get("last_error"):
            print("HATA:", status.get("last_error"))
            return 1

        print("OK: Test maili kuyruğa alındı.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
