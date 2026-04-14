from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


class Config:
    SECRET_KEY = "supersecretkey123"
    DB_PATH = BASE_DIR / "logs.db"
