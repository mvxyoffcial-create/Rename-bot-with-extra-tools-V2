from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from .. import database as db


def _settings_keyboard(user):
    s = user.get("settings", {})
    on_off = lambda v: "ON ✅" if v else "OFF ❌"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"🔧 Video Tools Menu: {on_off(s.get('video_tools', True))}",
                                   callback_data="set_toggle_video_tools")],
            [InlineKeyboardButton(f"📁 Auto-Rename: {on_off(s.get('auto_rename', False))}",
                                   callback_data="set_toggle_auto_rename")],
            [InlineKeyboardButton("🖼️ Custom Thumbnail: Set/Remove", callback_data="set_thumbnail")],
            [InlineKeyboardButton(
                f"📊 Progress Display: {'Detailed' if s.get('progress_detailed', True) else 'Simple'}",
                callback_data="set_toggle_progress")],
            [InlineKeyboardButton("🌐 Language: en", callback_data="set_language")],
            [InlineKeyboardButton("✖️ Close", callback_data="close_menu")],
        ]
    )


def register(app: Client):

    @app.on_message(filters.command("settings") & filters.private)
    async def settings_cmd(client: Client, message: Message):
        user = db.get_user(message.from_user.id)
        await message.reply_text("**⚙️ Settings**\n\nTap to toggle any option.", reply_markup=_settings_keyboard(user))

    @app.on_callback_query(filters.regex("^open_settings$"))
    async def open_settings_cb(client: Client, cq: CallbackQuery):
        user = db.get_user(cq.from_user.id)
        await cq.message.edit_text("**⚙️ Settings**\n\nTap to toggle any option.", reply_markup=_settings_keyboard(user))

    @app.on_callback_query(filters.regex("^set_toggle_video_tools$"))
    async def toggle_video_tools(client: Client, cq: CallbackQuery):
        user = db.get_user(cq.from_user.id)
        new_val = not user.get("settings", {}).get("video_tools", True)
        db.update_settings(cq.from_user.id, "video_tools", new_val)
        user = db.get_user(cq.from_user.id)
        await cq.message.edit_reply_markup(_settings_keyboard(user))
        await cq.answer(f"Video Tools Menu {'enabled' if new_val else 'disabled'}")

    @app.on_callback_query(filters.regex("^set_toggle_auto_rename$"))
    async def toggle_auto_rename(client: Client, cq: CallbackQuery):
        user = db.get_user(cq.from_user.id)
        new_val = not user.get("settings", {}).get("auto_rename", False)
        db.update_settings(cq.from_user.id, "auto_rename", new_val)
        user = db.get_user(cq.from_user.id)
        await cq.message.edit_reply_markup(_settings_keyboard(user))
        await cq.answer(f"Auto-Rename {'enabled' if new_val else 'disabled'}")

    @app.on_callback_query(filters.regex("^set_toggle_progress$"))
    async def toggle_progress(client: Client, cq: CallbackQuery):
        user = db.get_user(cq.from_user.id)
        new_val = not user.get("settings", {}).get("progress_detailed", True)
        db.update_settings(cq.from_user.id, "progress_detailed", new_val)
        user = db.get_user(cq.from_user.id)
        await cq.message.edit_reply_markup(_settings_keyboard(user))
        await cq.answer(f"Progress display set to {'Detailed' if new_val else 'Simple'}")

    @app.on_callback_query(filters.regex("^set_thumbnail$"))
    async def set_thumbnail_cb(client: Client, cq: CallbackQuery):
        await cq.answer()
        await cq.message.reply_text("Send me a photo to set as your custom thumbnail, or /delthumb to remove it.")

    @app.on_message(filters.command("delthumb") & filters.private)
    async def del_thumb(client: Client, message: Message):
        db.set_thumbnail(message.from_user.id, None)
        await message.reply_text("🗑️ Thumbnail removed.")

    @app.on_message(filters.photo & filters.private)
    async def save_thumb(client: Client, message: Message):
        db.set_thumbnail(message.from_user.id, message.photo.file_id)
        await message.reply_text("✅ Thumbnail saved.")

    @app.on_callback_query(filters.regex("^set_language$"))
    async def set_language_cb(client: Client, cq: CallbackQuery):
        await cq.answer("Only English is available right now.", show_alert=True)

    @app.on_callback_query(filters.regex("^close_menu$"))
    async def close_menu(client: Client, cq: CallbackQuery):
        await cq.message.delete()

    @app.on_callback_query(filters.regex("^open_help$"))
    async def open_help_cb(client: Client, cq: CallbackQuery):
        await cq.answer()
        await cq.message.reply_text(
            "**📖 How to use this bot**\n\n"
            "1. Send me a video file\n"
            "2. Reply with the new file name\n"
            "3. Choose tools from the menu\n"
            "4. Tap **Done** — I'll process and upload your file"
        )

    @app.on_callback_query(filters.regex("^open_premium$"))
    async def open_premium_cb(client: Client, cq: CallbackQuery):
        from ..config import Config
        await cq.answer()
        await cq.message.reply_text(
            f"**💎 Premium Benefits**\n\nUp to {Config.PREMIUM_MAX_FILE_SIZE // (1024*1024)}MB files, "
            f"unlimited processing, priority speed.\nContact @{Config.DEVELOPER_USERNAME} to upgrade."
        )
