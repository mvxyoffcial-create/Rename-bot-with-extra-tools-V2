from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant

from ..config import Config


async def not_joined_channels(client, user_id: int):
    """Return list of channel usernames the user has NOT joined."""
    missing = []
    for channel in Config.FORCE_SUB_CHANNELS:
        try:
            member = await client.get_chat_member(f"@{channel}", user_id)
            if member.status in ("left", "kicked"):
                missing.append(channel)
        except UserNotParticipant:
            missing.append(channel)
        except Exception:
            # Bot not admin in channel, or channel invalid — skip silently
            continue
    return missing


def join_keyboard(missing_channels):
    buttons = [[InlineKeyboardButton(f"📢 Join @{c}", url=f"https://t.me/{c}")] for c in missing_channels]
    buttons.append([InlineKeyboardButton("✅ I Joined", callback_data="check_fsub")])
    return InlineKeyboardMarkup(buttons)
