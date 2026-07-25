# 🎬 Video Bot — Advanced File Management & Processing

A Telegram bot (Pyrogram + MongoDB + FFmpeg) for renaming and processing video
files, with a live progress bar (Refresh button + `/stop_<task_id>`), stream
removal/extraction, audio/subtitle extraction, screenshots, sample clips,
force-subscribe, premium tiers, and a `/health` endpoint.

## 1. Requirements

- Python 3.10+
- MongoDB (local or Atlas)
- FFmpeg + ffprobe installed and on PATH (`sudo apt install ffmpeg`)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- `api_id` / `api_hash` from https://my.telegram.org

## 2. Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Configure

```bash
cp .env.example .env
```

Edit `.env` and fill in `API_ID`, `API_HASH`, `BOT_TOKEN`, `MONGO_URI`,
`ADMINS` (your Telegram user id), and `FORCE_SUB_CHANNELS` (leave blank to
disable force-subscribe). The bot must be an **admin** in any force-sub
channel to check membership.

## 4. Run

```bash
python3 main.py
```

The health check endpoint is available at `http://localhost:8000/health`.

## 5. Project layout

```
videobot/
├── main.py                  # entry point, wires plugins + health server
├── requirements.txt
├── .env.example
└── bot/
    ├── config.py             # loads .env into Config
    ├── database.py           # MongoDB helpers (users/tasks/files)
    ├── health.py             # aiohttp /health server
    ├── utils/
    │   ├── progress.py        # progress bar text/keyboard + throttled edits
    │   ├── ffmpeg_utils.py     # ffprobe/ffmpeg wrappers
    │   └── force_sub.py        # force-subscribe checks
    └── plugins/
        ├── start.py            # /start /help /about /info /premium
        ├── settings.py         # /settings menu + thumbnail
        ├── admin.py            # /stats /broadcast /addpremium ... (admins only)
        └── rename.py           # core workflow: rename → tools menu → process → upload
```

## 6. How the progress bar works

`bot/utils/progress.py` renders the same layout as the reference screenshot
(`Task Running: n/steps`, bar, processed/size/speed/ETA/elapsed, engine,
user, `/stop_<task_id>`), with two inline buttons under every progress
message:

- **🔄 Refresh** — calls `update_progress(..., force_update=True)`, which
  bypasses the normal edit throttle so the numbers update immediately.
- **🛑 Stop** — cancels the task (`db.cancel_task`) and stops further
  processing; the same effect as sending `/stop_<task_id>` as a command.

Regular download/processing/upload callbacks are throttled to one edit every
`Config.PROGRESS_UPDATE_INTERVAL` seconds (default 3s) to stay well under
Telegram's edit rate limits.

## 7. Notes / things to double-check before going to production

- This is a functional reference implementation, not a hardened production
  deploy — add proper logging, retries, and disk-space checks before scaling
  to real traffic.
- `send_document` uploads with Pyrogram/Bot API cap at 2GB unless you run a
  **local Bot API server** — for true 4GB uploads you need
  `telegram-bot-api` running locally and pointed at by Pyrogram's
  `Client(..., ipv6=False)` local-server config.
- FFmpeg stream removal/extraction uses `-c copy` (no re-encoding) so it's
  fast, but that means it only works for removing/extracting whole streams,
  not re-encoding to different codecs.
- Force-subscribe requires the bot to be an admin in each channel listed in
  `FORCE_SUB_CHANNELS`.

Developer: **@Spidey2189**
