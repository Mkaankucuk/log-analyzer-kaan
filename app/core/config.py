from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parents[2]


class Config:
    SECRET_KEY = "supersecretkey123"
    DB_PATH = BASE_DIR / "logs.db"
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
    OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "45"))
