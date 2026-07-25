# ============================================================
#  bot/config.py
#  Hardcoded configuration — NO environment variables used.
#  Fill in your real values below, then run: python3 main.py
# ============================================================


class Config:
    # ---- Telegram API credentials (https://my.telegram.org) ----
    API_ID = 36282056                     # <-- your api_id (integer)
    API_HASH = "3a948acece533f362b4c90b2b3c14b60"     # <-- your api_hash

    # ---- Bot token (from @BotFather) ----
    BOT_TOKEN = "8285873350:AAHVx971B_3r-lJM804MkH288qqjMWHq_CI"

    # ---- MongoDB ----
    MONGO_URI = "mongodb+srv://filmzi2120_db_user:zero8907@cluster0.zyau0re.mongodb.net/?appName=Cluster0"
    DB_NAME = "videobot"

    # ---- Admins: Telegram user IDs allowed to use admin commands ----
    ADMINS = [8312532076]                # <-- put your Telegram user id(s) here

    # ---- Force-subscribe channels (bot must be admin in each) ----
    # Leave as an empty list [] to disable force-subscribe.
    FORCE_SUB_CHANNELS = ["spideyoffcail", "mvxyoffcail"]

    # ---- File size limits (in MB) ----
    FREE_MAX_FILE_SIZE_MB = 2048
    PREMIUM_MAX_FILE_SIZE_MB = 4096
    FREE_MAX_FILE_SIZE = FREE_MAX_FILE_SIZE_MB * 1024 * 1024
    PREMIUM_MAX_FILE_SIZE = PREMIUM_MAX_FILE_SIZE_MB * 1024 * 1024

    # ---- Daily free-tier usage limit ----
    FREE_DAILY_LIMIT = 10

    # ---- Health check server ----
    HEALTH_PORT = 8000

    # ---- Misc ----
    DEVELOPER_USERNAME = "Spidey2189"
    DOWNLOAD_DIR = "downloads"
    WORKERS = 500

    # Progress bar refresh: min seconds between edits per task (Telegram rate limits)
    PROGRESS_UPDATE_INTERVAL = 3
