import json, os
from datetime import date

QUOTA_FILE = os.path.join(os.path.expanduser("~"), ".subtitle_app_quota.json")
DAILY_LIMIT = 10000

def _load():
    if not os.path.exists(QUOTA_FILE):
        return {"day": str(date.today()), "count": 0}
    with open(QUOTA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(data):
    with open(QUOTA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

def check_and_consume(n_requests: int = 1) -> None:
    data = _load()
    today = str(date.today())

    if data.get("day") != today:
        data = {"day": today, "count": 0}

    if data["count"] + n_requests > DAILY_LIMIT:
        raise RuntimeError(f"Daily AI quota exceeded ({data['count']}/{DAILY_LIMIT}).")

    data["count"] += n_requests
    _save(data)
