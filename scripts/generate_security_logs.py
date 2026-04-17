from faker import Faker
from pathlib import Path
import pandas as pd
import random
from datetime import datetime, timedelta

fake = Faker()

APIS = ["user-api", "payment-api", "order-api", "auth-api", "inventory-api"]
TEAMS = ["team-alpha", "team-beta", "team-gamma", "team-delta"]
ENVS = ["dev", "staging", "prod"]
METHODS = ["GET", "POST", "PUT", "DELETE"]
ERROR_TYPES = ["ClientError", "ServerError", "Timeout", "AuthError", "RateLimit"]

ERROR_WEIGHTS = [0.40, 0.25, 0.15, 0.10, 0.10]

STATUS_MAP = {
    "ClientError": [400, 401, 403, 404],
    "ServerError": [500, 502, 503],
    "Timeout": [504],
    "AuthError": [401],
    "RateLimit": [429]
}

ROOT_CAUSES = {
    "ClientError": ["Invalid request", "Missing parameter", "Schema validation error"],
    "ServerError": ["Database failure", "Null pointer exception", "Internal service crash"],
    "Timeout": ["Slow network", "Upstream timeout", "Gateway timeout"],
    "AuthError": ["Expired token", "Invalid token", "Missing authorization scope"],
    "RateLimit": ["Too many requests", "Burst traffic detected"]
}


def generate_security_logs(row_count=50000):
    rows = []
    start_time = datetime(2024, 1, 1, 0, 0, 0)

    for i in range(row_count):
        timestamp = start_time + timedelta(seconds=i * random.randint(1, 5))

        error_type = random.choices(ERROR_TYPES, weights=ERROR_WEIGHTS)[0]
        status_code = random.choice(STATUS_MAP[error_type])
        latency = random.randint(100, 8000)

        rows.append({
            "timestamp": timestamp,
            "api": random.choice(APIS),
            "team": random.choice(TEAMS),
            "env": random.choice(ENVS),
            "method": random.choice(METHODS),
            "endpoint": f"/v1/{fake.word()}",
            "status_code": status_code,
            "error_type": error_type,
            "root_cause": random.choice(ROOT_CAUSES[error_type]),
            "latency_ms": latency
        })

    return pd.DataFrame(rows)


def save_security_logs(df: pd.DataFrame):
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    data_dir.mkdir(exist_ok=True)

    output_path = data_dir / "fake_security_logs.csv"
    df.to_csv(output_path, index=False)

    print(f"Fake security log üretildi: {output_path}")


if __name__ == "__main__":
    dataframe = generate_security_logs()
    save_security_logs(dataframe)