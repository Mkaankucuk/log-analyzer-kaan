from pathlib import Path
import random
import pandas as pd


METHODS = ["GET", "POST", "PUT", "DELETE"]
ENDPOINTS = ["Interact1", "Interact2", "Interact3", "Popular", "Other"]


def generate_access_logs(row_count=50000):
    rows = []
    start_ts = 1402815600

    for _ in range(row_count):
        timestamp = start_ts + random.random() * 1000

        method = random.choice(METHODS)
        status = random.choices(
            [200, 201, 302, 400, 404, 405, 500],
            weights=[50, 10, 10, 10, 10, 5, 5]
        )[0]

        latency = random.randint(20, 300)
        endpoint = random.choice(ENDPOINTS)

        rows.append({
            "Timestamp": round(timestamp, 6),
            "latency": latency,
            "status": status,
            "method": method,
            "endpoint": endpoint
        })

    return pd.DataFrame(rows)


def save_access_logs(df):
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    data_dir.mkdir(exist_ok=True)

    output_path = data_dir / "requestlogs_generated.csv"
    df.to_csv(output_path, sep=";", index=False)

    print(f"Fake access logs oluşturuldu: {output_path}")


if __name__ == "__main__":
    dataframe = generate_access_logs()
    save_access_logs(dataframe)