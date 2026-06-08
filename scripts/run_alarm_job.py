"""Manual cron tick: python scripts/run_alarm_job.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.env_loader import load_env

load_env()

from app import create_app  # noqa: E402
from app.services.alarm_job_service import get_job_status, run_alarm_job  # noqa: E402


def main() -> int:
    app = create_app()
    with app.app_context():
        result = run_alarm_job(manual=True)
        status = get_job_status()
        print("Rows scanned:", result.get("rows_scanned", status.get("rows_scanned")))
        print("Alarms created:", result.get("alarms_created", status.get("alarms_created_last_run")))
        print("Active alarms:", status.get("active_alarms"))
        if result.get("error") or status.get("last_error"):
            print("Error:", result.get("error") or status.get("last_error"))
            return 1
        print("OK")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
