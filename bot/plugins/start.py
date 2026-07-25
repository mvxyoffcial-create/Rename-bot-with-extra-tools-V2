import asyncio
import logging
import random
import string

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from .. import database as db
from ..config import Config
from ..utils.force_sub import join_keyboard, not_joined_channels

logger = logging.getLogger(__name__)

STICKER_ID = "CAACAgIAAxkBAAEQZtFpgEdROhGouBVFD3e0K-YjmVHwsgACtCMAAphLKUjeub7NKlvk2TgE"


def _rand_id():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


WELCOME_TEXT = """<b>ʜᴇʏ, {user_name}! 👋</b>

ɪ'ᴍ ᴀ <b>ᴠɪᴅᴇᴏ ᴘʀᴏᴄᴇssɪɴɢ ʙᴏᴛ</b> 🎬
ɪ ᴄᴀɴ ʀᴇɴᴀᴍᴇ, ᴘʀᴏᴄᴇss, ᴀɴᴅ ᴍᴀɴᴀɢᴇ ʏᴏᴜʀ ᴠɪᴅᴇᴏs! 📹

<b>📤 Sᴇɴᴅ ᴍᴇ ᴀ ᴠɪᴅᴇᴏ</b>
<b>✏️ Gɪᴠᴇ ɪᴛ ᴀ ɴᴇᴡ ɴᴀᴍᴇ</b>
<b>⚡ Pʀᴏᴄᴇss ᴡɪᴛʜ ᴀᴅᴠᴀɴᴄᴇᴅ ᴛᴏᴏʟs</b>

<b>🚀 Fᴇᴀᴛᴜʀᴇs:</b>
• Rᴇɴᴀᴍᴇ ғɪʟᴇs
• Rᴇᴍᴏᴠᴇ sᴛʀᴇᴀᴍs
• Exᴛʀᴀᴄᴛ ᴀᴜᴅɪᴏ/sᴜʙᴛɪᴛʟᴇs
• Tᴀᴋᴇ sᴄʀᴇᴇɴsʜᴏᴛs
• Cʀᴇᴀᴛᴇ sᴀᴍᴘʟᴇ ᴄʟɪᴘs

👨‍💻 Dᴇᴠᴇʟᴏᴘᴇʀ: @{dev}
"""


def register(app: Client):

    @app.on_message(filters.command("start") & filters.private)
    async def start_cmd(client: Client, message: Message):
        # Safe DB Call
        try:
            db.upsert_user(message.from_user)
        except Exception as e:
            logger.error(f"Database error in start_cmd: {e}")

        # Safe Force Sub Check
        if getattr(Config, "FORCE_SUB_CHANNELS", None):
            try:
                missing = await not_joined_channels(client, message.from_user.id)
                if missing:
                    await message.reply_text(
                        "🔒 **Please join our channel(s) to use this bot.**\n\n"
                        "After joining, tap **I Joined** below.",
                        reply_markup=join_keyboard(missing),
                    )
                    return
            except Exception as e:
                logger.error(f"Force sub check error: {e}")

        sticker_msg = None
        try:
            sticker_msg = await message.reply_sticker(STICKER_ID)
        except Exception:
            pass

        await message.reply_text(
            WELCOME_TEXT.format(
                user_name=message.from_user.first_name,
                dev=getattr(Config, "DEVELOPER_USERNAME", "admin"),
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("⚙️ Settings", callback_data="open_settings"),
                        InlineKeyboardButton("ℹ️ Help", callback_data="open_help"),
                    ],
                    [InlineKeyboardButton("💎 Premium", callback_data="open_premium")],
                ]
            ),
        )

        if sticker_msg:
            await asyncio.sleep(2)
            try:
                await sticker_msg.delete()
            except Exception:
                pass

    @app.on_message(filters.command("help") & filters.private)
    async def help_cmd(client: Client, message: Message):
        await message.reply_text(
            "**📖 How to use this bot**\n\n"
            "1. Send me a video file (up to 4GB for premium, 2GB free)\n"
            "2. Reply with the new file name\n"
            "3. Choose tools from the menu (stream remove, extract audio, etc.)\n"
            "4. Tap **Done** — I'll process and upload your file\n\n"
            "Use /status to check a running task and /cancel to stop it.\n"
            "Use /settings to configure the bot for your account."
        )

    @app.on_message(filters.command("about") & filters.private)
    async def about_cmd(client: Client, message: Message):
        dev_user = getattr(Config, "DEVELOPER_USERNAME", "admin")
        await message.reply_text(
            "**🎬 Video Processing Bot**\n\n"
            "Built with Pyrogram + FFmpeg + MongoDB\n"
            f"Developer: @{dev_user}\n"
            "Supports rename, stream removal/extraction, audio/subtitle extraction, "
            "screenshots and sample clips, all with a live progress bar."
        )

    @app.on_message(filters.command("info") & filters.private)
    async def info_cmd(client: Client, message: Message):
        try:
            user = db.get_user(message.from_user.id) or {}
            is_prem = db.is_premium(message.from_user.id)
            usage = db.usage_today(message.from_user.id)
        except Exception as e:
            logger.error(f"DB Error in info_cmd: {e}")
            user, is_prem, usage = {}, False, 0

        premium = "✅ Yes" if is_prem else "❌ No"
        text = (
            f"**👤 User Info**\n\n"
            f"Name: {message.from_user.first_name}\n"
            f"Username: @{message.from_user.username}\n"
            f"User ID: `{message.from_user.id}`\n"
            f"Premium: {premium}\n"
            f"Total files processed: {user.get('total_files', 0)}\n"
            f"Used today: {usage}\n"
        )
        try:
            photos = [p async for p in client.get_chat_photos(message.from_user.id, limit=1)]
        except Exception:
            photos = []

        if photos:
            await message.reply_photo(photos[0].file_id, caption=text)
        else:
            await message.reply_text(text)

    @app.on_message(filters.command("premium") & filters.private)
    async def premium_cmd(client: Client, message: Message):
        max_size = getattr(Config, "PREMIUM_MAX_FILE_SIZE", 4294967296) // (1024 * 1024)
        dev_user = getattr(Config, "DEVELOPER_USERNAME", "admin")
        await message.reply_text(
            "**💎 Premium Benefits**\n\n"
            f"• Up to {max_size}MB files\n"
            "• Unlimited daily processes\n"
            "• All advanced tools unlocked\n"
            "• Priority processing speed\n"
            "• Priority support\n"
            "• Batch processing\n\n"
            f"Contact @{dev_user} to upgrade."
        )
