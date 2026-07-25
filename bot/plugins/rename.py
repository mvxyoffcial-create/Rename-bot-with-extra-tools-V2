import os
import time
import uuid
import asyncio

from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
)

from ..config import Config
from .. import database as db
from ..utils import ffmpeg_utils as ff
from ..utils.progress import update_progress, human_size

# In-memory conversational state: user_id -> dict
PENDING = {}

TOOLS = [
    ("remove_stream", "Stream Remove 🗑️"),
    ("extract_stream", "Stream Extract 📤"),
    ("extract_audio", "Extract Audio 🎵"),
    ("extract_subtitle", "Extract Subtitle 📝"),
    ("screenshot", "Take Screenshot 📸"),
    ("sample", "Sample Video 🎬"),
]


def _tools_keyboard(task_id, selected):
    rows = []
    for key, label in TOOLS:
        tick = "✅ " if key in selected else "⬜ "
        rows.append([InlineKeyboardButton(tick + label, callback_data=f"tool_{task_id}_{key}")])
    rows.append([InlineKeyboardButton("✅ Done", callback_data=f"tooldone_{task_id}")])
    return InlineKeyboardMarkup(rows)


def _new_task_id():
    return uuid.uuid4().hex[:16]


def _max_size(user_id):
    return Config.PREMIUM_MAX_FILE_SIZE if db.is_premium(user_id) else Config.FREE_MAX_FILE_SIZE


def register(app: Client):

    # ---------------------------------------------------------- file intake
    @app.on_message((filters.video | filters.document) & filters.private)
    async def on_file(client: Client, message: Message):
        user_id = message.from_user.id
        if db.is_banned(user_id):
            await message.reply_text("🚫 You are banned from using this bot.")
            return

        media = message.video or message.document
        file_size = media.file_size or 0

        if file_size > _max_size(user_id):
            limit_mb = _max_size(user_id) // (1024 * 1024)
            await message.reply_text(f"❌ File too large. Your limit is {limit_mb}MB.")
            return

        if not db.is_premium(user_id) and db.usage_today(user_id) >= Config.FREE_DAILY_LIMIT:
            await message.reply_text(
                f"❌ Daily free limit reached ({Config.FREE_DAILY_LIMIT}/day). "
                f"Get /premium for unlimited processing."
            )
            return

        task_id = _new_task_id()
        original_name = media.file_name or f"video_{task_id}.mp4"
        db.create_task(task_id, user_id, original_name, file_size, file_path=None)

        PENDING[user_id] = {"stage": "await_name", "task_id": task_id, "message_id": message.id}

        await message.reply_text(
            f"📁 Got your file: **{original_name}** ({human_size(file_size)})\n\n"
            "✏️ Please reply with the **new name** for this file (without extension is fine)."
        )

    # ---------------------------------------------------------- rename text
    @app.on_message(filters.text & filters.private & ~filters.command([
        "start", "help", "about", "settings", "rename", "premium", "status",
        "cancel", "stats", "broadcast", "addpremium", "removepremium",
        "ban", "unban", "restart", "delthumb",
    ]))
    async def on_text(client: Client, message: Message):
        user_id = message.from_user.id
        state = PENDING.get(user_id)
        if not state:
            return  # not in a conversation flow, ignore

        task_id = state["task_id"]

        if state["stage"] == "await_name":
            new_name = message.text.strip()
            db.update_task(task_id, new_name=new_name, status="downloading")
            status_msg = await message.reply_text("📥 Starting download...")

            task = db.get_task(task_id)
            os.makedirs(Config.DOWNLOAD_DIR, exist_ok=True)
            local_path = os.path.join(Config.DOWNLOAD_DIR, f"{task_id}_{task['original_name']}")

            start_time = time.time()
            loop = asyncio.get_event_loop()

            async def dl_progress(current, total):
                await update_progress(
                    client, status_msg.chat.id, status_msg.id, task_id, "downloading",
                    current, total, start_time, message.from_user.first_name, user_id,
                )

            # find the original message that had the file
            orig_id = state["message_id"]
            orig_msg = await client.get_messages(message.chat.id, orig_id)
            try:
                await orig_msg.download(file_name=local_path, progress=dl_progress)
            except Exception as e:
                await status_msg.edit_text(f"❌ Download failed: {e}")
                PENDING.pop(user_id, None)
                return

            db.update_task(task_id, file_path=local_path, status="choosing_tools")
            PENDING[user_id] = {"stage": "choosing_tools", "task_id": task_id, "status_msg_id": status_msg.id}

            await status_msg.edit_text(
                f"✅ Downloaded as **{new_name}**\n\n"
                "🎬 **Video Processing** — choose tools, then tap Done:",
                reply_markup=_tools_keyboard(task_id, []),
            )
            return

        if state["stage"] == "await_screenshot_time":
            await _run_screenshot(client, message, task_id, message.text.strip())
            PENDING.pop(user_id, None)
            return

        if state["stage"] == "await_sample_duration":
            try:
                dur = int(message.text.strip())
            except ValueError:
                dur = 30
            await _run_sample(client, message, task_id, dur)
            PENDING.pop(user_id, None)
            return

    # ------------------------------------------------------- tool toggling
    @app.on_callback_query(filters.regex(r"^tool_"))
    async def toggle_tool(client: Client, cq: CallbackQuery):
        _, task_id, key = cq.data.split("_", 2)
        actions = db.toggle_action(task_id, key)
        await cq.message.edit_reply_markup(_tools_keyboard(task_id, actions))
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^tooldone_"))
    async def tools_done(client: Client, cq: CallbackQuery):
        task_id = cq.data.split("_", 1)[1]
        task = db.get_task(task_id)
        actions = task.get("selected_actions", [])
        user_id = cq.from_user.id

        if not actions:
            await cq.answer()
            await _finalize_rename_only(client, cq.message, task_id)
            return

        await cq.answer()

        if "remove_stream" in actions or "extract_stream" in actions or "extract_subtitle" in actions:
            streams, _ = await ff.probe_streams(task["file_path"])
            db.update_task(task_id, _streams_cache=streams) if False else None
            PENDING[user_id] = {"stage": "choosing_streams", "task_id": task_id, "streams": streams, "selected": []}
            mode = "remove_stream" if "remove_stream" in actions else (
                "extract_stream" if "extract_stream" in actions else "extract_subtitle")
            await cq.message.edit_text(
                _stream_list_text(streams, mode),
                reply_markup=_stream_keyboard(task_id, streams, [], mode),
            )
            return

        # No stream selection needed — run remaining simple actions
        await _run_simple_actions(client, cq.message, task_id, actions)

    # -------------------------------------------------- stream selection UI
    def _stream_list_text(streams, mode):
        title = {
            "remove_stream": "🗑️ Select streams to REMOVE",
            "extract_stream": "📤 Select ONE stream to EXTRACT",
            "extract_subtitle": "📝 Select subtitle stream to extract",
        }[mode]
        lines = [f"**{title}**\n"]
        for s in streams:
            if mode == "extract_subtitle" and s["codec_type"] != "subtitle":
                continue
            lines.append(ff.describe_stream(s))
        lines.append("\nTap streams below, then press ✅ Done.")
        return "\n".join(lines)

    def _stream_keyboard(task_id, streams, selected, mode):
        rows = []
        for s in streams:
            if mode == "extract_subtitle" and s["codec_type"] != "subtitle":
                continue
            tick = "☑️ " if s["index"] in selected else "☐ "
            rows.append([InlineKeyboardButton(
                tick + ff.describe_stream(s), callback_data=f"strm_{task_id}_{s['index']}"
            )])
        rows.append([InlineKeyboardButton("✅ Done", callback_data=f"strmdone_{task_id}_{mode}")])
        return rows and InlineKeyboardMarkup(rows)

    @app.on_callback_query(filters.regex(r"^strm_"))
    async def toggle_stream(client: Client, cq: CallbackQuery):
        _, task_id, idx = cq.data.split("_", 2)
        idx = int(idx)
        state = PENDING.get(cq.from_user.id)
        if not state or state.get("task_id") != task_id:
            await cq.answer("Session expired, please resend the file.", show_alert=True)
            return
        selected = state.setdefault("selected", [])
        mode = None
        # infer mode by re-reading current message markup isn't trivial; store mode too
        mode = state.get("mode")
        if mode is None:
            # first toggle: derive from task's selected_actions
            task = db.get_task(task_id)
            actions = task.get("selected_actions", [])
            mode = "remove_stream" if "remove_stream" in actions else (
                "extract_stream" if "extract_stream" in actions else "extract_subtitle")
            state["mode"] = mode

        if mode == "extract_stream":
            state["selected"] = [idx]  # single-select
        else:
            if idx in selected:
                selected.remove(idx)
            else:
                selected.append(idx)

        await cq.message.edit_reply_markup(_stream_keyboard(task_id, state["streams"], state["selected"], mode))
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^strmdone_"))
    async def streams_done(client: Client, cq: CallbackQuery):
        _, task_id, mode = cq.data.split("_", 2)
        state = PENDING.get(cq.from_user.id, {})
        selected = state.get("selected", [])
        await cq.answer()

        if not selected:
            await cq.message.reply_text("⚠️ No streams selected, skipping this step.")
        else:
            db.update_task(task_id, streams_selected={mode: selected})

        task = db.get_task(task_id)
        actions = [a for a in task.get("selected_actions", []) if a != mode]
        db.update_task(task_id, selected_actions=actions)

        if selected:
            await _run_stream_action(client, cq.message, task_id, mode, selected)

        remaining = [a for a in actions if a not in ("remove_stream", "extract_stream", "extract_subtitle")]
        if remaining:
            await _run_simple_actions(client, cq.message, task_id, remaining)
        else:
            await _maybe_finish(client, cq.message, task_id)

    # ------------------------------------------------------------ /status
    @app.on_message(filters.command("status") & filters.private)
    async def status_cmd(client: Client, message: Message):
        state = PENDING.get(message.from_user.id)
        if not state:
            await message.reply_text("No active task.")
            return
        task = db.get_task(state["task_id"])
        await message.reply_text(
            f"**Task:** `{task['task_id']}`\n**Status:** {task['status']}\n**File:** {task['original_name']}"
        )

    @app.on_message(filters.command("cancel") & filters.private)
    async def cancel_cmd(client: Client, message: Message):
        state = PENDING.pop(message.from_user.id, None)
        if not state:
            await message.reply_text("No active task to cancel.")
            return
        db.cancel_task(state["task_id"])
        await message.reply_text("🛑 Task cancelled.")

    @app.on_message(filters.command("rename") & filters.private)
    async def rename_cmd(client: Client, message: Message):
        await message.reply_text("📤 Send me the video/document file you want to rename and process.")

    # /stop_<task_id> pattern commands
    @app.on_message(filters.regex(r"^/stop_([a-zA-Z0-9]+)") & filters.private)
    async def stop_task_cmd(client: Client, message: Message):
        task_id = message.matches[0].group(1)
        task = db.get_task(task_id)
        if not task or task["user_id"] != message.from_user.id:
            await message.reply_text("⚠️ Task not found.")
            return
        db.cancel_task(task_id)
        PENDING.pop(message.from_user.id, None)
        await message.reply_text(f"🛑 Task `{task_id}` stopped.")

    @app.on_callback_query(filters.regex(r"^stop_"))
    async def stop_task_cb(client: Client, cq: CallbackQuery):
        task_id = cq.data.split("_", 1)[1]
        task = db.get_task(task_id)
        if not task or task["user_id"] != cq.from_user.id:
            await cq.answer("Task not found.", show_alert=True)
            return
        db.cancel_task(task_id)
        PENDING.pop(cq.from_user.id, None)
        await cq.answer("Task stopped.")
        await cq.message.edit_text(f"🛑 Task `{task_id}` stopped by user.")

    # Refresh button — force_update bypasses the throttle so the tap always
    # shows a fresh reading immediately.
    @app.on_callback_query(filters.regex(r"^refresh_"))
    async def refresh_cb(client: Client, cq: CallbackQuery):
        task_id = cq.data.split("_", 1)[1]
        task = db.get_task(task_id)
        if not task:
            await cq.answer("Task not found.", show_alert=True)
            return
        current = task.get("progress_current", task.get("progress", 0))
        total = task.get("file_size", 0)
        start_time = task.get("_start_time", time.time())
        await update_progress(
            client, cq.message.chat.id, cq.message.id, task_id, task.get("status", "processing"),
            current, total, start_time, cq.from_user.first_name, cq.from_user.id,
            force_update=True,
        )
        await cq.answer("Refreshed ✅")

    # ---------------------------------------------------- screenshot/sample prompts
    @app.on_callback_query(filters.regex(r"^ask_ss_"))
    async def ask_screenshot_time(client: Client, cq: CallbackQuery):
        task_id = cq.data.split("_", 2)[2]
        PENDING[cq.from_user.id] = {"stage": "await_screenshot_time", "task_id": task_id}
        await cq.answer()
        await cq.message.reply_text("⏱️ Send timestamp (e.g. `00:00:10`) or `default` for 5s in.")

    @app.on_callback_query(filters.regex(r"^ask_sample_"))
    async def ask_sample_duration(client: Client, cq: CallbackQuery):
        task_id = cq.data.split("_", 2)[2]
        PENDING[cq.from_user.id] = {"stage": "await_sample_duration", "task_id": task_id}
        await cq.answer()
        await cq.message.reply_text("⏱️ Send sample duration in seconds (default 30).")

    # ------------------------------------------------------------- runners
    async def _finalize_rename_only(client, message, task_id):
        task = db.get_task(task_id)
        await _upload_result(client, message, task_id, task["file_path"], task["new_name"])

    async def _run_simple_actions(client, message, task_id, actions):
        task = db.get_task(task_id)
        for action in actions:
            if action == "extract_audio":
                await _run_extract_audio(client, message, task_id)
            elif action == "screenshot":
                await message.reply_text(
                    "📸 Send timestamp for the screenshot:",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("Choose timestamp", callback_data=f"ask_ss_{task_id}")]]
                    ),
                )
                return
            elif action == "sample":
                await message.reply_text(
                    "🎬 Choose sample clip duration:",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("Choose duration", callback_data=f"ask_sample_{task_id}")]]
                    ),
                )
                return
        await _maybe_finish(client, message, task_id)

    async def _run_stream_action(client, message, task_id, mode, selected):
        task = db.get_task(task_id)
        duration = await ff.get_duration(task["file_path"])
        status = await message.reply_text("⚙️ Processing streams...")
        start_time = time.time()

        async def prog(current, total):
            await update_progress(
                client, status.chat.id, status.id, task_id, "processing", current, total,
                start_time, message.chat.first_name or "user", task["user_id"],
            )

        base, ext = os.path.splitext(task["file_path"])
        try:
            if mode == "remove_stream":
                out_path = f"{base}_streamremoved{ext}"
                await ff.remove_streams(task["file_path"], out_path, selected, prog, duration)
                db.update_task(task_id, file_path=out_path)
                await status.edit_text("✅ Streams removed.")
            elif mode == "extract_stream":
                idx = selected[0]
                out_path = f"{base}_stream{idx}{ext}"
                await ff.extract_stream(task["file_path"], out_path, idx, prog, duration)
                await status.edit_text("✅ Stream extracted, uploading...")
                await _upload_result(client, message, task_id, out_path,
                                      f"{task['new_name']}_stream_{idx}")
            elif mode == "extract_subtitle":
                idx = selected[0]
                out_path = f"{base}_sub{idx}.srt"
                await ff.extract_subtitle(task["file_path"], out_path, idx)
                await status.edit_text("✅ Subtitle extracted, uploading...")
                await _upload_result(client, message, task_id, out_path,
                                      f"{task['new_name']}_subtitle")
        except Exception as e:
            await status.edit_text(f"❌ Processing failed: {e}")

    async def _run_extract_audio(client, message, task_id):
        task = db.get_task(task_id)
        duration = await ff.get_duration(task["file_path"])
        status = await message.reply_text("🎵 Extracting audio...")
        start_time = time.time()

        async def prog(current, total):
            await update_progress(
                client, status.chat.id, status.id, task_id, "processing", current, total,
                start_time, "user", task["user_id"],
            )

        base, _ = os.path.splitext(task["file_path"])
        out_path = f"{base}_audio.mp3"
        try:
            await ff.extract_audio(task["file_path"], out_path, prog, duration)
            await status.edit_text("✅ Audio extracted, uploading...")
            await _upload_result(client, message, task_id, out_path, f"{task['new_name']}_audio", audio=True)
        except Exception as e:
            await status.edit_text(f"❌ Audio extraction failed: {e}")

    async def _run_screenshot(client, message, task_id, timestamp_text):
        task = db.get_task(task_id)
        ts = "00:00:05" if timestamp_text.lower() == "default" else timestamp_text
        base, _ = os.path.splitext(task["file_path"])
        out_path = f"{base}_screenshot_1.jpg"
        status = await message.reply_text("📸 Taking screenshot...")
        try:
            await ff.take_screenshot(task["file_path"], out_path, ts)
            await status.edit_text("✅ Screenshot taken, uploading...")
            await client.send_photo(message.chat.id, out_path,
                                     caption=f"{task['new_name']}_screenshot_1.jpg")
        except Exception as e:
            await status.edit_text(f"❌ Screenshot failed: {e}")
            return
        await _maybe_finish(client, message, task_id)

    async def _run_sample(client, message, task_id, dur):
        task = db.get_task(task_id)
        base, ext = os.path.splitext(task["file_path"])
        out_path = f"{base}_sample{ext}"
        status = await message.reply_text("🎬 Creating sample clip...")
        try:
            await ff.sample_video(task["file_path"], out_path, dur)
            await status.edit_text("✅ Sample ready, uploading...")
            await _upload_result(client, message, task_id, out_path, f"{task['new_name']}_sample")
        except Exception as e:
            await status.edit_text(f"❌ Sample creation failed: {e}")

    async def _maybe_finish(client, message, task_id):
        task = db.get_task(task_id)
        if task["status"] not in ("completed",):
            await _upload_result(client, message, task_id, task["file_path"], task["new_name"])

    async def _upload_result(client, message, task_id, path, display_name, audio=False):
        task = db.get_task(task_id)
        user_id = task["user_id"]
        status = await message.reply_text(f"📤 Uploading **{display_name}**...")
        start_time = time.time()

        async def up_progress(current, total):
            await update_progress(
                client, status.chat.id, status.id, task_id, "uploading", current, total,
                start_time, "user", user_id,
            )

        thumb = None
        u = db.get_user(user_id)
        if u.get("thumbnail"):
            thumb = u["thumbnail"]

        try:
            if audio:
                await client.send_audio(message.chat.id, path, file_name=display_name,
                                         progress=up_progress, thumb=thumb)
            else:
                await client.send_document(message.chat.id, path, file_name=os.path.basename(path),
                                            progress=up_progress, thumb=thumb)
            db.update_task(task_id, status="completed")
            db.bump_usage(user_id)
            await status.edit_text(f"✅ Completed! **{display_name}**")
        except Exception as e:
            await status.edit_text(f"❌ Upload failed: {e}")
        finally:
            PENDING.pop(user_id, None)
