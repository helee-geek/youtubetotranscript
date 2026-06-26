# YouTube to Transcript — Python Demo

A small demo inspired by [YouTubeToTranscript.com](https://youtubetotranscript.com): paste a YouTube URL, fetch captions, copy the text.

## FastAPI vs Flask — which one?

**This demo uses FastAPI** because it fits this project well:

| | FastAPI | Flask |
|---|---|---|
| API docs | Built-in Swagger at `/docs` | Needs an extension |
| Validation | Pydantic models | Manual |
| Async | Native (good for long Whisper jobs) | Possible but less natural |
| Speed | Faster for APIs | Fine for simple apps |

Flask is a solid choice for a tiny static page. For an API + optional long-running transcription, **FastAPI is the better pick**.

## Libraries used

| Library | Role |
|---|---|
| **[FastAPI](https://fastapi.tiangolo.com/)** | Web framework & REST API |
| **[uvicorn](https://www.uvicorn.org/)** | ASGI server |
| **[youtube-transcript-api](https://pypi.org/project/youtube-transcript-api/)** | Primary: fetch existing YouTube captions (fast, no download) |
| **[faster-whisper](https://pypi.org/project/faster-whisper/)** | Fallback: transcribe audio when captions are missing |
| **[yt-dlp](https://pypi.org/project/yt-dlp/)** | Download YouTube audio for the Whisper fallback |
| **[Jinja2](https://jinja.palletsprojects.com/)** | HTML templates |

## How it works

1. **First try** — `youtube-transcript-api` fetches YouTube's own captions.
2. **Fallback** — if captions are disabled or missing, `yt-dlp` downloads audio and `faster-whisper` transcribes it (slower; first run downloads the Whisper model).

## Setup

```bash
cd youtubetotranscript
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Whisper fallback also needs FFmpeg:**

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

## Run

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000)

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## Free fix: "YouTube blocked this request" on Render / cloud

YouTube blocks **datacenter IPs** (Render, Railway, etc.). There is no free proxy that fixes that on cloud hosting.

**Free tool: [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) (`cloudflared`)** — run the app on your laptop (home IP works) and get a public URL to share.

### Setup (one time)

```bash
pip install -r requirements.txt

# Install cloudflared
sudo apt install cloudflared          # Ubuntu/Debian
# brew install cloudflared            # macOS
```

### Before your demo

```bash
chmod +x scripts/run-demo-tunnel.sh
./scripts/run-demo-tunnel.sh
```

Share the `https://….trycloudflare.com` URL it prints. **Keep the terminal open** during the presentation.

| | Render (free) | Tunnel demo (free) |
|---|---|---|
| Cost | $0 | $0 |
| YouTube works | ❌ Blocked | ✅ Home IP |
| Laptop on during demo | No | Yes |

## Fix: "YouTube is blocking requests" on localhost

If **your own IP** is temporarily blocked from too many tests:

1. **Wait 30–60 minutes** without making requests.
2. **Slow down** — click "Get Transcript" once, wait for the result.
3. **Use mobile hotspot** — different IP.

## API example

```bash
curl -X POST http://localhost:8000/api/transcript \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

Optional fields: `language`, `translate_to`, `use_whisper_fallback`.

## Notes

- Caption fetch is instant for most public videos.
- Whisper fallback is CPU-heavy; the default model is `base`. Change `model_size` in `services/transcript_service.py` if needed.
- Respect YouTube's terms of service and copyright when using transcripts.
