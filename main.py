from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from youtube_transcript_api._errors import IpBlocked, RequestBlocked

from services.transcript_service import (
    extract_video_id,
    get_transcript,
    list_available_languages,
    normalize_lang,
    translate_plain_text,
)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="YouTube to Transcript Demo",
    description="Fetch YouTube captions via youtube-transcript-api, with faster-whisper fallback.",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


class TranscriptRequest(BaseModel):
    url: str = Field(..., description="YouTube URL or 11-character video ID")
    language: str | None = Field(None, description="Preferred caption language code, e.g. en")
    translate_to: str | None = Field(None, description="Translate captions to this language code")
    use_whisper_fallback: bool = Field(
        True,
        description="Use faster-whisper when YouTube captions are unavailable",
    )


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


class TranslateRequest(BaseModel):
    text: str = Field(..., description="Text to translate")
    source_lang: str = Field(..., description="Source language code, e.g. hi")
    target_lang: str = Field(..., description="Target language code, e.g. en")


@app.post("/api/translate")
async def api_translate(body: TranslateRequest):
    try:
        translated = translate_plain_text(
            body.text,
            normalize_lang(body.source_lang),
            normalize_lang(body.target_lang),
        )
        return {
            "ok": True,
            "text": translated,
            "language_code": normalize_lang(body.target_lang),
            "source": "text_translation",
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Translation failed: {exc}") from exc


@app.post("/api/transcript")
async def api_transcript(body: TranscriptRequest):
    try:
        result = get_transcript(
            body.url,
            language=body.language,
            translate_to=body.translate_to,
            use_whisper_fallback=body.use_whisper_fallback,
        )
        return {"ok": True, **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (IpBlocked, RequestBlocked) as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc


@app.get("/api/languages")
async def api_languages(url: str):
    video_id = extract_video_id(url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL or video ID.")
    try:
        languages = list_available_languages(video_id)
        return {"ok": True, "video_id": video_id, "languages": languages}
    except (IpBlocked, RequestBlocked) as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
