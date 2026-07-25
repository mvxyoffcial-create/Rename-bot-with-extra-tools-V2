# ============================================================
#  Dockerfile — Video Processing Telegram Bot
#  Build:  docker build -t videobot .
#  Run:    docker run -d --name videobot -p 8000:8000 videobot
#  (Make sure bot/config.py has your real API_ID/API_HASH/BOT_TOKEN
#   filled in BEFORE building the image.)
# ============================================================

FROM python:3.11-slim

# ffmpeg/ffprobe are required for stream removal, extraction,
# screenshots, and sample clips.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the bot (config.py must already contain your
# real credentials since there is no .env / environment injection)
COPY . .

# Downloaded/processed files live here — mount a volume in production
RUN mkdir -p downloads

# Health check endpoint
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python3 -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://localhost:8000/health').status==200 else sys.exit(1)"

CMD ["python3", "main.py"]

