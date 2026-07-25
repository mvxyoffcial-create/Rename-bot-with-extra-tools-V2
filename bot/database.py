import datetime
from pymongo import MongoClient

from .config import Config

_client = MongoClient(Config.MONGO_URI)
_db = _client[Config.DB_NAME]

users_col = _db["users"]
tasks_col = _db["tasks"]
files_col = _db["files"]


# ---------------------------------------------------------------- users ----

DEFAULT_SETTINGS = {
    "video_tools": True,
    "auto_rename": False,
    "progress_detailed": True,
    "language": "en",
}


def get_user(user_id: int):
    user = users_col.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "first_name": "",
            "last_name": "",
            "username": "",
            "is_premium": False,
            "premium_until": None,
            "total_files": 0,
            "joined_date": datetime.datetime.utcnow(),
            "is_banned": False,
            "settings": DEFAULT_SETTINGS.copy(),
            "thumbnail": None,
            "used_today": 0,
            "last_used": None,
        }
        users_col.insert_one(user)
    return user


def upsert_user(message_from_user):
    users_col.update_one(
        {"user_id": message_from_user.id},
        {
            "$set": {
                "first_name": message_from_user.first_name or "",
                "last_name": message_from_user.last_name or "",
                "username": message_from_user.username or "",
            },
            "$setOnInsert": {
                "user_id": message_from_user.id,
                "is_premium": False,
                "premium_until": None,
                "total_files": 0,
                "joined_date": datetime.datetime.utcnow(),
                "is_banned": False,
                "settings": DEFAULT_SETTINGS.copy(),
                "thumbnail": None,
                "used_today": 0,
                "last_used": None,
            },
        },
        upsert=True,
    )
    return get_user(message_from_user.id)


def is_premium(user_id: int) -> bool:
    user = get_user(user_id)
    if not user.get("is_premium"):
        return False
    until = user.get("premium_until")
    if until and until < datetime.datetime.utcnow():
        users_col.update_one({"user_id": user_id}, {"$set": {"is_premium": False}})
        return False
    return True


def add_premium(user_id: int, days: int):
    until = datetime.datetime.utcnow() + datetime.timedelta(days=days)
    users_col.update_one(
        {"user_id": user_id},
        {"$set": {"is_premium": True, "premium_until": until}},
        upsert=True,
    )
    return until


def remove_premium(user_id: int):
    users_col.update_one({"user_id": user_id}, {"$set": {"is_premium": False, "premium_until": None}})


def ban_user(user_id: int):
    users_col.update_one({"user_id": user_id}, {"$set": {"is_banned": True}}, upsert=True)


def unban_user(user_id: int):
    users_col.update_one({"user_id": user_id}, {"$set": {"is_banned": False}})


def is_banned(user_id: int) -> bool:
    user = get_user(user_id)
    return bool(user.get("is_banned"))


def update_settings(user_id: int, key: str, value):
    users_col.update_one({"user_id": user_id}, {"$set": {f"settings.{key}": value}})


def set_thumbnail(user_id: int, file_id: str):
    users_col.update_one({"user_id": user_id}, {"$set": {"thumbnail": file_id}})


def bump_usage(user_id: int):
    now = datetime.datetime.utcnow()
    user = get_user(user_id)
    last_used = user.get("last_used")
    used_today = user.get("used_today", 0)
    if last_used is None or last_used.date() != now.date():
        used_today = 0
    used_today += 1
    users_col.update_one(
        {"user_id": user_id},
        {"$set": {"used_today": used_today, "last_used": now}, "$inc": {"total_files": 1}},
    )
    return used_today


def usage_today(user_id: int) -> int:
    user = get_user(user_id)
    last_used = user.get("last_used")
    if last_used is None or last_used.date() != datetime.datetime.utcnow().date():
        return 0
    return user.get("used_today", 0)


def total_users() -> int:
    return users_col.count_documents({})


def all_user_ids():
    return [u["user_id"] for u in users_col.find({}, {"user_id": 1})]


# ---------------------------------------------------------------- tasks ----

def create_task(task_id: str, user_id: int, original_name: str, file_size: int, file_path: str):
    task = {
        "user_id": user_id,
        "task_id": task_id,
        "file_path": file_path,
        "new_name": None,
        "original_name": original_name,
        "file_size": file_size,
        "status": "waiting_name",
        "progress": 0,
        "speed": 0.0,
        "eta": 0,
        "elapsed": 0,
        "started_at": datetime.datetime.utcnow(),
        "completed_at": None,
        "selected_actions": [],
        "streams_selected": {},
        "output_path": None,
        "thumbnail_path": None,
        "cancelled": False,
    }
    tasks_col.insert_one(task)
    return task


def get_task(task_id: str):
    return tasks_col.find_one({"task_id": task_id})


def update_task(task_id: str, **fields):
    tasks_col.update_one({"task_id": task_id}, {"$set": fields})


def cancel_task(task_id: str):
    tasks_col.update_one({"task_id": task_id}, {"$set": {"cancelled": True, "status": "cancelled"}})


def is_cancelled(task_id: str) -> bool:
    task = get_task(task_id)
    return bool(task and task.get("cancelled"))


def toggle_action(task_id: str, action: str):
    task = get_task(task_id)
    if not task:
        return []
    actions = set(task.get("selected_actions", []))
    if action in actions:
        actions.remove(action)
    else:
        actions.add(action)
    actions = list(actions)
    update_task(task_id, selected_actions=actions)
    return actions


def active_tasks_count() -> int:
    return tasks_col.count_documents({"status": {"$in": ["downloading", "processing", "uploading", "waiting_name", "choosing_tools"]}})
