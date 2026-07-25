import datetime
from aiohttp import web
import psutil

from .config import Config
from . import database as db


async def health_handler(request):
    return web.json_response({
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "workers": Config.WORKERS,
        "active_tasks": db.active_tasks_count(),
        "total_users": db.total_users(),
        "cpu_usage": psutil.cpu_percent(),
        "memory_usage": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage("/").percent,
        "bot_running": True,
    })


async def root_handler(request):
    return web.json_response({"message": "Video Bot is running.", "health": "/health"})


def create_app():
    app = web.Application()
    app.router.add_get("/", root_handler)
    app.router.add_get("/health", health_handler)
    return app


async def run_health_server():
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", Config.HEALTH_PORT)
    await site.start()
    return runner
