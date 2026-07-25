import asyncio
import logging

from pyrogram import Client, idle  # <--- Imported idle

from bot.config import Config
from bot.health import run_health_server
from bot.plugins import start, settings, admin, rename, fsub

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

app = Client(
    "videobot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    workers=Config.WORKERS,
)

# Register all plugin handlers on the client
for module in (start, settings, admin, rename, fsub):
    module.register(app)


async def main():
    if not Config.API_ID or not Config.API_HASH or not Config.BOT_TOKEN:
        raise SystemExit(
            "Missing API_ID / API_HASH / BOT_TOKEN. Copy .env.example to .env and fill it in."
        )

    runner = await run_health_server()
    logging.info(f"Health check server running on port {Config.HEALTH_PORT}")

    await app.start()
    logging.info("Video Bot started.")
    try:
        await idle()  # <--- Replaced asyncio.Event().wait()
    finally:
        await app.stop()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
