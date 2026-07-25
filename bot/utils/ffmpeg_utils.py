import asyncio
import json
import os


async def probe_streams(file_path: str):
    """Return a list of stream dicts using ffprobe (video/audio/subtitle)."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", file_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {err.decode(errors='ignore')}")
    data = json.loads(out.decode(errors="ignore"))
    streams = []
    for s in data.get("streams", []):
        streams.append(
            {
                "index": s.get("index"),
                "codec_type": s.get("codec_type"),
                "codec_name": s.get("codec_name"),
                "width": s.get("width"),
                "height": s.get("height"),
                "language": s.get("tags", {}).get("language", "und"),
                "channels": s.get("channels"),
            }
        )
    return streams, data.get("format", {})


def describe_stream(s: dict) -> str:
    if s["codec_type"] == "video":
        res = f"{s.get('width')}x{s.get('height')}" if s.get("width") else ""
        return f"Stream {s['index']}: {s['codec_name'].upper()} {res} [Video]"
    if s["codec_type"] == "audio":
        ch = f"{s.get('channels')}ch" if s.get("channels") else ""
        return f"Stream {s['index']}: {s['codec_name'].upper()} ({s.get('language')}) {ch} [Audio]"
    if s["codec_type"] == "subtitle":
        return f"Stream {s['index']}: {s['codec_name'].upper()} ({s.get('language')}) [Subtitle]"
    return f"Stream {s['index']}: {s['codec_name']} [{s['codec_type']}]"


async def run_ffmpeg(args: list, progress_cb=None, duration: float = None):
    """Run an ffmpeg command, optionally reporting progress via -progress pipe:1."""
    cmd = ["ffmpeg", "-y", "-progress", "pipe:1", "-nostats", *args]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
    )
    current_time = 0.0
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        line = line.decode(errors="ignore").strip()
        if line.startswith("out_time_ms=") and progress_cb and duration:
            try:
                out_time_ms = int(line.split("=")[1])
                current_time = out_time_ms / 1_000_000
                await progress_cb(min(current_time, duration), duration)
            except (ValueError, IndexError):
                pass
    await proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg processing failed")


async def remove_streams(input_path: str, output_path: str, remove_indices: list, progress_cb=None, duration=None):
    args = ["-i", input_path, "-map", "0"]
    for idx in remove_indices:
        args += ["-map", f"-0:{idx}"]
    args += ["-c", "copy", output_path]
    await run_ffmpeg(args, progress_cb, duration)


async def extract_stream(input_path: str, output_path: str, stream_index: int, progress_cb=None, duration=None):
    args = ["-i", input_path, "-map", f"0:{stream_index}", "-c", "copy", output_path]
    await run_ffmpeg(args, progress_cb, duration)


async def extract_audio(input_path: str, output_path: str, progress_cb=None, duration=None):
    args = ["-i", input_path, "-vn", "-acodec", "libmp3lame", "-q:a", "2", output_path]
    await run_ffmpeg(args, progress_cb, duration)


async def extract_subtitle(input_path: str, output_path: str, stream_index: int):
    args = ["-i", input_path, "-map", f"0:{stream_index}", output_path]
    await run_ffmpeg(args)


async def take_screenshot(input_path: str, output_path: str, timestamp: str = "00:00:05"):
    args = ["-ss", timestamp, "-i", input_path, "-frames:v", "1", "-q:v", "2", output_path]
    await run_ffmpeg(args)


async def sample_video(input_path: str, output_path: str, duration_sec: int = 30, start: str = "00:00:00"):
    args = ["-ss", start, "-i", input_path, "-t", str(duration_sec), "-c", "copy", output_path]
    await run_ffmpeg(args)


async def get_duration(input_path: str) -> float:
    _, fmt = await probe_streams(input_path)
    try:
        return float(fmt.get("duration", 0))
    except (TypeError, ValueError):
        return 0.0
