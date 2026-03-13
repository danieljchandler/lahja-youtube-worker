# lahja-youtube-worker

A RunPod serverless worker that downloads YouTube audio for the Lahja Arabic language learning app. It uses yt-dlp to fetch audio in Opus format (64 kbps) and uploads it to Supabase Storage. No GPU is required — this worker runs on a standard CPU instance.

Used by the Lahja app for:
- YouTube audio pipeline
- Line-by-line transcript playback
- Flashcard audio

## Environment Variables

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL, e.g. `https://xxxx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Supabase service role secret key |
| `SUPABASE_BUCKET` | Supabase Storage bucket name, e.g. `audio` |

## Example Input / Output

**Input**
```json
{
  "input": {
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  }
}
```

**Output (success)**
```json
{
  "storage_url": "https://xxxx.supabase.co/storage/v1/object/public/audio/youtube/dQw4w9WgXcQ/550e8400-e29b-41d4-a716-446655440000.opus",
  "video_id": "dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up",
  "duration": 213,
  "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
  "channel": "Rick Astley",
  "format": "opus"
}
```

**Output (error)**
```json
{
  "error": "Video is private"
}
```

Possible error values: `"Video is private"`, `"Video is age-restricted"`, `"Video is unavailable"`, or a generic `"Download failed: ..."` message.

## Deployment

1. **Build and push the Docker image**
   ```bash
   docker build -t your-dockerhub-username/lahja-youtube-worker:latest .
   docker push your-dockerhub-username/lahja-youtube-worker:latest
   ```

2. **Create a RunPod Serverless endpoint**
   - Go to [RunPod Serverless](https://www.runpod.io/console/serverless)
   - Click **New Endpoint** → **Custom Container**
   - Container image: `your-dockerhub-username/lahja-youtube-worker:latest`
   - Select a **CPU** instance (no GPU needed)
   - Add the environment variables listed above

3. **Call the endpoint** from your Lahja app using the RunPod API or SDK.