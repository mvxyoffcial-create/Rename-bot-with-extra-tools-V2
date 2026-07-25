"""
Progress bar system that mirrors the reference screenshot:

    Task Running: 1/20
    1.Download:
    [██████████░░░░░░░░] 45%
    Processed: 450MB
    Size: 1.0GB
    Speed: 12.5MB/s
    ETA: 45s
    Elapsed: 2m 15s
    Upload: Telegram
    Engine: TDLib v1.8.66
    <name> (<id>)
    /stop_<task_id>

    [🔄 Refresh]

Supports force_update=True to bypass the rate-limit throttle (used by the
Refresh button so the user always sees a fresh number when they tap it).
"""

import time
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified, FloodWait

from ..config import Config

# task_id -> last edit timestamp, keeps us under Telegram's edit rate limit
_last_edit = {}

STAGE_LABELS = {
    "downloading": "Download",
    "processing": "Processing",
    "uploading": "Upload",
}


def human_size(n: float) -> str:
    if n is None:
        return "0B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f}{unit}" if unit != "B" else f"{int(n)}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def human_time(seconds) -> str:
    if seconds is None or seconds < 0:
        return "-"
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def make_bar(percent: float, length: int = 14) -> str:
    percent = max(0, min(100, percent))
    filled = int(length * percent / 100)
    return "█" * filled + "░" * (length - filled)


def render_progress_text(task_id, stage, current, total, speed, elapsed, user_name, user_id,
                          step=1, total_steps=1, engine="TDLib v1.8.66"):
    percent = (current / total * 100) if total else 0
    eta = ((total - current) / speed) if speed and total else None
    bar = make_bar(percent)
    label = STAGE_LABELS.get(stage, stage.capitalize())

    text = (
        f"**Task Running: {step}/{total_steps}**\n\n"
        f"**1.{label}:**\n"
        f"[{bar}] {percent:.0f}%\n"
        f"**Processed:** {human_size(current)}\n"
        f"**Size:** {human_size(total)}\n"
        f"**Speed:** {human_size(speed)}/s\n"
        f"**ETA:** {human_time(eta)}\n"
        f"**Elapsed:** {human_time(elapsed)}\n"
        f"**Upload:** Telegram\n"
        f"**Engine:** {engine}\n"
        f"{user_name} (`{user_id}`)\n"
        f"/stop_{task_id}"
    )
    return text


def progress_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{task_id}")],
            [InlineKeyboardButton("🛑 Stop", callback_data=f"stop_{task_id}")],
        ]
    )


async def update_progress(client, chat_id, message_id, task_id, stage, current, total,
                           start_time, user_name, user_id, force_update=False,
                           step=1, total_steps=1):
    """
    Edit the progress message. Throttled to Config.PROGRESS_UPDATE_INTERVAL
    seconds unless force_update=True (used by download/upload callbacks that
    fire very frequently, and always honoured when the user taps Refresh).
    """
    now = time.time()
    last = _last_edit.get(task_id, 0)
    if not force_update and (now - last) < Config.PROGRESS_UPDATE_INTERVAL:
        return

    _last_edit[task_id] = now
    elapsed = now - start_time
    speed = current / elapsed if elapsed > 0 else 0

    text = render_progress_text(
        task_id, stage, current, total, speed, elapsed, user_name, user_id,
        step=step, total_steps=total_steps,
    )

    try:
        await client.edit_message_text(
            chat_id, message_id, text, reply_markup=progress_keyboard(task_id)
        )
    except MessageNotModified:
        pass
    except FloodWait as e:
        time.sleep(e.value)
    except Exception:
        # Never let a progress-bar edit crash the transfer
        pass


def make_pyrogram_progress_callback(client, chat_id, message_id, task_id, stage,
                                     start_time, user_name, user_id, loop,
                                     step=1, total_steps=1):
    """
    Returns a sync callback usable as Pyrogram's download/upload `progress=`
    argument, which internally schedules the async edit on the given loop.
    """

    def _cb(current, total):
        import asyncio
        asyncio.run_coroutine_threadsafe(
            update_progress(
                client, chat_id, message_id, task_id, stage, current, total,
                start_time, user_name, user_id, step=step, total_steps=total_steps,
            ),
            loop,
        )

    return _cb
