import os
import tempfile
import uuid

import runpod
import yt_dlp
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
SUPABASE_BUCKET = os.environ["SUPABASE_BUCKET"]

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

ERROR_KEYWORDS = {
    "private video": "Video is private",
    "age-restricted": "Video is age-restricted",
    "age restricted": "Video is age-restricted",
    "not available": "Video is unavailable",
    "video unavailable": "Video is unavailable",
    "this video is unavailable": "Video is unavailable",
}


def classify_error(message: str) -> str:
    lower = message.lower()
    for keyword, friendly in ERROR_KEYWORDS.items():
        if keyword in lower:
            return friendly
    return f"Download failed: {message}"


def handler(job):
    job_input = job.get("input", {})
    youtube_url = job_input.get("youtube_url")

    if not youtube_url:
        return {"error": "Missing required input: youtube_url"}

    with tempfile.TemporaryDirectory() as tmpdir:
        output_template = os.path.join(tmpdir, "%(id)s.%(ext)s")

        ydl_opts = {
            "format": "bestaudio[ext=opus]/bestaudio",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "opus",
                    "preferredquality": "64",
                }
            ],
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
        except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError) as exc:
            return {"error": classify_error(str(exc))}
        except Exception as exc:
            return {"error": classify_error(str(exc))}

        video_id = info.get("id", "unknown")
        title = info.get("title", "")
        duration = info.get("duration")
        thumbnail = info.get("thumbnail", "")
        channel = info.get("uploader") or info.get("channel", "")

        audio_filename = f"{video_id}.opus"
        audio_path = os.path.join(tmpdir, audio_filename)

        if not os.path.exists(audio_path):
            candidates = [
                f for f in os.listdir(tmpdir) if f.endswith(".opus")
            ]
            if not candidates:
                return {"error": "Audio file not found after download"}
            audio_path = os.path.join(tmpdir, candidates[0])

        storage_path = f"youtube/{video_id}/{uuid.uuid4()}.opus"

        try:
            with open(audio_path, "rb") as audio_file:
                supabase.storage.from_(SUPABASE_BUCKET).upload(
                    storage_path,
                    audio_file,
                    {"content-type": "audio/ogg; codecs=opus"},
                )
        except Exception as exc:
            return {"error": f"Upload failed: {exc}"}

        storage_url = (
            f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{storage_path}"
        )

        return {
            "storage_url": storage_url,
            "video_id": video_id,
            "title": title,
            "duration": duration,
            "thumbnail": thumbnail,
            "channel": channel,
            "format": "opus",
        }


runpod.serverless.start({"handler": handler})
