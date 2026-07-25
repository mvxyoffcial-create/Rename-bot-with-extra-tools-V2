import os
from dotenv import load_dotenv

load_dotenv()


def _int(name, default=0):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _list(name):
    raw = os.environ.get(name, "")
    return [x.strip() for x in raw.split(",") if x.strip()]


class Config:
    API_ID = _int("API_ID")
    API_HASH = os.environ.get("API_HASH", "")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME = os.environ.get("DB_NAME", "videobot")

    ADMINS = [int(x) for x in _list("ADMINS") if x.isdigit()]

    FORCE_SUB_CHANNELS = _list("FORCE_SUB_CHANNELS")

    FREE_MAX_FILE_SIZE = _int("FREE_MAX_FILE_SIZE_MB", 2048) * 1024 * 1024
    PREMIUM_MAX_FILE_SIZE = _int("PREMIUM_MAX_FILE_SIZE_MB", 4096) * 1024 * 1024
    FREE_DAILY_LIMIT = _int("FREE_DAILY_LIMIT", 10)

    HEALTH_PORT = _int("HEALTH_PORT", 8000)

    DEVELOPER_USERNAME = os.environ.get("DEVELOPER_USERNAME", "Spidey2189")
    DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "downloads")
    WORKERS = _int("WORKERS", 500)

    # Progress bar refresh: min seconds between edits per task (Telegram rate limits)
    PROGRESS_UPDATE_INTERVAL = 3
