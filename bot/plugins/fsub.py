from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from ..utils.force_sub import not_joined_channels, join_keyboard


def register(app: Client):

    @app.on_callback_query(filters.regex("^check_fsub$"))
    async def check_fsub(client: Client, cq: CallbackQuery):
        missing = await not_joined_channels(client, cq.from_user.id)
        if missing:
            await cq.answer("You still haven't joined all channels.", show_alert=True)
            await cq.message.edit_reply_markup(join_keyboard(missing))
            return
        await cq.answer("✅ Verified! You can use the bot now.", show_alert=True)
        await cq.message.edit_text("✅ Thanks for joining! Send /start again to begin.")
