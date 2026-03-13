import os
import tempfile
import uuid

import requests
import runpod
import yt_dlp

SUPABASE_FUNCTION_URL = os.environ["SUPABASE_FUNCTION_URL"]  # e.g. https://ovscskaijvclaxelkdyf.supabase.co/functions/v1/receive-audio
RUNPOD_CALLBACK_SECRET = os.environ["RUNPOD_CALLBACK_SECRET"]

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

        audio_path = os.path.join(tmpdir, f"{video_id}.opus")

        if not os.path.exists(audio_path):
            candidates = [f for f in os.listdir(tmpdir) if f.endswith(".opus")]
            if not candidates:
                return {"error": "Audio file not found after download"}
            audio_path = os.path.join(tmpdir, candidates[0])

        try:
            with open(audio_path, "rb") as audio_file:
                response = requests.post(
                    SUPABASE_FUNCTION_URL,
                    headers={"Authorization": f"Bearer {RUNPOD_CALLBACK_SECRET}"},
                    files={"audio": (f"{video_id}.opus", audio_file, "audio/ogg; codecs=opus")},
                    data={
                        "video_id": video_id,
                        "source_url": youtube_url,
                        "title": title,
                        "duration": str(duration) if duration else "",
                        "thumbnail": thumbnail,
                        "channel": channel,
                    },
                    timeout=120,
                )
            response.raise_for_status()
            result = response.json()
        except requests.HTTPError as exc:
            return {"error": f"Edge function error {exc.response.status_code}: {exc.response.text}"}
        except Exception as exc:
            return {"error": f"Upload failed: {exc}"}

        return {
            "storage_url": result.get("storage_url"),
            "video_id": video_id,
            "title": title,
            "duration": duration,
            "thumbnail": thumbnail,
            "channel": channel,
            "format": "opus",
        }


runpod.serverless.start({"handler": handler})
