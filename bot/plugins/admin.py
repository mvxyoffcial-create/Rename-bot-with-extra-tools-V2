import asyncio
import psutil

from pyrogram import Client, filters
from pyrogram.types import Message

from ..config import Config
from .. import database as db


def admin_filter():
    return filters.create(lambda _, __, m: bool(m.from_user) and m.from_user.id in Config.ADMINS)


def register(app: Client):

    @app.on_message(filters.command("stats") & filters.private & admin_filter())
    async def stats_cmd(client: Client, message: Message):
        await message.reply_text(
            "**📊 Bot Statistics**\n\n"
            f"👥 Total users: {db.total_users()}\n"
            f"⚙️ Active tasks: {db.active_tasks_count()}\n"
            f"🖥️ CPU: {psutil.cpu_percent()}%\n"
            f"💾 RAM: {psutil.virtual_memory().percent}%\n"
            f"💿 Disk: {psutil.disk_usage('/').percent}%\n"
        )

    @app.on_message(filters.command("broadcast") & filters.private & admin_filter())
    async def broadcast_cmd(client: Client, message: Message):
        if not message.reply_to_message:
            await message.reply_text("Reply to a message with /broadcast to send it to all users.")
            return
        ids = db.all_user_ids()
        sent, failed = 0, 0
        status = await message.reply_text(f"Broadcasting to {len(ids)} users...")
        for uid in ids:
            try:
                await message.reply_to_message.copy(uid)
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.05)
        await status.edit_text(f"✅ Broadcast complete.\nSent: {sent}\nFailed: {failed}")

    @app.on_message(filters.command("addpremium") & filters.private & admin_filter())
    async def add_premium_cmd(client: Client, message: Message):
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply_text("Usage: /addpremium <user_id> [days=30]")
            return
        user_id = int(parts[1])
        days = int(parts[2]) if len(parts) > 2 else 30
        until = db.add_premium(user_id, days)
        await message.reply_text(f"✅ Premium granted to `{user_id}` until {until:%Y-%m-%d}.")

    @app.on_message(filters.command("removepremium") & filters.private & admin_filter())
    async def remove_premium_cmd(client: Client, message: Message):
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply_text("Usage: /removepremium <user_id>")
            return
        db.remove_premium(int(parts[1]))
        await message.reply_text("✅ Premium removed.")

    @app.on_message(filters.command("ban") & filters.private & admin_filter())
    async def ban_cmd(client: Client, message: Message):
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply_text("Usage: /ban <user_id>")
            return
        db.ban_user(int(parts[1]))
        await message.reply_text("🚫 User banned.")

    @app.on_message(filters.command("unban") & filters.private & admin_filter())
    async def unban_cmd(client: Client, message: Message):
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply_text("Usage: /unban <user_id>")
            return
        db.unban_user(int(parts[1]))
        await message.reply_text("✅ User unbanned.")

    @app.on_message(filters.command("restart") & filters.private & admin_filter())
    async def restart_cmd(client: Client, message: Message):
        await message.reply_text("♻️ Restarting...")
        import os
        os.execl(os.sys.executable, os.sys.executable, *os.sys.argv)
