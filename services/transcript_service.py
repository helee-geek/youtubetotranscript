import re
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    IpBlocked,
    NoTranscriptFound,
    NotTranslatable,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
)
from youtube_transcript_api.proxies import GenericProxyConfig

from services.cache import (
    get_cached_source,
    get_cached_translation,
    set_cached_source,
    set_cached_translation,
)
from services.config import HTTP_PROXY, HTTPS_PROXY, IP_BLOCK_HELP
from services.ytdlp_service import fetch_transcript_ytdlp, list_languages_ytdlp

VIDEO_ID_PATTERNS = [
    re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})"),
    re.compile(r"^([a-zA-Z0-9_-]{11})$"),
]


def extract_video_id(url_or_id: str) -> str | None:
    value = url_or_id.strip()
    for pattern in VIDEO_ID_PATTERNS:
        match = pattern.search(value)
        if match:
            return match.group(1)
    return None


def get_youtube_api() -> YouTubeTranscriptApi:
    proxy_config = None
    if HTTP_PROXY or HTTPS_PROXY:
        proxy_config = GenericProxyConfig(
            http_url=HTTP_PROXY or HTTPS_PROXY,
            https_url=HTTPS_PROXY or HTTP_PROXY,
        )
    return YouTubeTranscriptApi(proxy_config=proxy_config)


def list_available_languages(video_id: str) -> list[dict]:
    try:
        return _list_languages_api(video_id)
    except (IpBlocked, RequestBlocked):
        return list_languages_ytdlp(video_id)


def _list_languages_api(video_id: str) -> list[dict]:
    api = get_youtube_api()
    transcript_list = api.list(video_id)
    languages = []
    seen = set()
    for transcript in transcript_list:
        code = transcript.language_code
        if code in seen:
            continue
        seen.add(code)
        languages.append(
            {
                "code": code,
                "name": transcript.language,
                "is_generated": transcript.is_generated,
                "is_translatable": transcript.is_translatable,
            }
        )
    return languages


def normalize_lang(code: str | None) -> str:
    if not code:
        return ""
    return code.split("-")[0].lower()


def translate_plain_text(text: str, source_lang: str, target_lang: str) -> str:
    source_lang = normalize_lang(source_lang)
    target_lang = normalize_lang(target_lang)
    if not text.strip() or source_lang == target_lang:
        return text

    cached = get_cached_translation(text, source_lang, target_lang)
    if cached is not None:
        return cached

    translated = _translate_text_parallel(text, source_lang, target_lang)
    set_cached_translation(text, source_lang, target_lang, translated)
    return translated


def translate_transcript_text(result: dict, target_lang: str) -> dict:
    source_lang = normalize_lang(result["language_code"])
    target_lang = normalize_lang(target_lang)
    if source_lang == target_lang:
        return result

    translated_text = translate_plain_text(result["text"], source_lang, target_lang)

    return {
        **result,
        "source": "text_translation",
        "language": target_lang,
        "language_code": target_lang,
        "text": translated_text,
        "source_text": result["text"],
        "source_language_code": result["language_code"],
        "snippets": result["snippets"],
    }


def _split_text_chunks(full_text: str, max_chunk: int = 1800) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(full_text):
        end = min(start + max_chunk, len(full_text))
        if end < len(full_text):
            split_at = full_text.rfind(" ", start, end)
            if split_at > start:
                end = split_at
        chunk = full_text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end if end > start else start + 1
    return chunks


def _translate_text_parallel(text: str, source_lang: str, target_lang: str) -> str:
    chunks = _split_text_chunks(text)
    if not chunks:
        return text
    if len(chunks) == 1:
        return _translate_chunk_worker(source_lang, target_lang, chunks[0])

    workers = min(len(chunks), 12)
    translated_by_index: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_translate_chunk_worker, source_lang, target_lang, chunk): index
            for index, chunk in enumerate(chunks)
        }
        for future in as_completed(futures):
            index = futures[future]
            translated_by_index[index] = future.result()

    return " ".join(translated_by_index[i] for i in range(len(chunks)))


def _translate_chunk_worker(source_lang: str, target_lang: str, text: str) -> str:
    from deep_translator import GoogleTranslator

    translator = GoogleTranslator(source=source_lang or "auto", target=target_lang)
    return _translate_chunk(translator, text)


def _translate_chunk(translator, text: str) -> str:
    try:
        return translator.translate(text)
    except Exception:
        if len(text) <= 500:
            return text
        mid = len(text) // 2
        split_at = text.rfind(" ", 0, mid)
        if split_at <= 0:
            split_at = mid
        left = _translate_chunk(translator, text[:split_at].strip())
        right = _translate_chunk(translator, text[split_at:].strip())
        return f"{left} {right}".strip()


def _build_result_from_fetched(video_id: str, fetched) -> dict:
    snippets = fetched.to_raw_data()
    text = " ".join(snippet["text"] for snippet in snippets)
    return {
        "video_id": video_id,
        "source": "youtube_captions",
        "language": fetched.language,
        "language_code": fetched.language_code,
        "is_generated": fetched.is_generated,
        "text": text,
        "snippets": snippets,
    }


def _find_transcript(transcript_list, language: str | None):
    if language:
        return transcript_list.find_transcript([language])
    try:
        return transcript_list.find_transcript(["hi", "en"])
    except NoTranscriptFound:
        return next(iter(transcript_list))


def fetch_source_transcript(video_id: str, language: str | None = None) -> dict:
    cached = get_cached_source(video_id, language)
    if cached is not None:
        return cached

    try:
        api = get_youtube_api()
        transcript_list = api.list(video_id)
        transcript = _find_transcript(transcript_list, language)
        fetched = transcript.fetch()
        result = _build_result_from_fetched(video_id, fetched)
    except (IpBlocked, RequestBlocked):
        result = fetch_transcript_ytdlp(video_id, language)

    set_cached_source(video_id, language, result)
    return result


def fetch_youtube_transcript(
    video_id: str,
    language: str | None = None,
    translate_to: str | None = None,
) -> dict:
    api = get_youtube_api()
    transcript_list = api.list(video_id)
    transcript = _find_transcript(transcript_list, language)

    if translate_to and translate_to != transcript.language_code:
        if not transcript.is_translatable:
            raise NotTranslatable(video_id)
        transcript = transcript.translate(translate_to)

    fetched = transcript.fetch()
    return _build_result_from_fetched(video_id, fetched)


def fetch_transcript_with_fallback(
    video_id: str,
    language: str | None = None,
    translate_to: str | None = None,
) -> dict:
    try:
        return fetch_youtube_transcript(video_id, language, translate_to)
    except (IpBlocked, RequestBlocked):
        if translate_to:
            source = fetch_transcript_ytdlp(video_id, language)
            if source["language_code"] == translate_to:
                return source
            return translate_transcript_text(source, translate_to)
        return fetch_transcript_ytdlp(video_id, language)


def transcribe_with_whisper(video_id: str, language: str | None = None, model_size: str = "base") -> dict:
    import yt_dlp
    from faster_whisper import WhisperModel

    from services.ytdlp_service import ytdlp_options

    with tempfile.TemporaryDirectory() as tmp_dir:
        audio_path = Path(tmp_dir) / "audio.mp3"
        url = f"https://www.youtube.com/watch?v={video_id}"

        ydl_opts = ytdlp_options(
            format="bestaudio/best",
            outtmpl=str(audio_path.with_suffix("")),
            postprocessors=[
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "128",
                }
            ],
        )

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not audio_path.exists():
            candidates = list(Path(tmp_dir).glob("audio.*"))
            if not candidates:
                raise RuntimeError("Failed to download audio from YouTube.")
            audio_path = candidates[0]

        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        transcribe_kwargs = {"beam_size": 5}
        if language:
            transcribe_kwargs["language"] = language
        segments, info = model.transcribe(str(audio_path), **transcribe_kwargs)

        snippets = []
        text_parts = []
        for segment in segments:
            snippets.append(
                {
                    "text": segment.text.strip(),
                    "start": segment.start,
                    "duration": segment.end - segment.start,
                }
            )
            text_parts.append(segment.text.strip())

    return {
        "video_id": video_id,
        "source": "faster_whisper",
        "language": info.language,
        "language_code": info.language,
        "is_generated": True,
        "text": " ".join(text_parts),
        "snippets": snippets,
    }


def get_transcript_with_translation(
    video_id: str,
    language: str | None,
    translate_to: str,
) -> dict:
    translate_to = normalize_lang(translate_to)
    cached = get_cached_source(video_id, language)
    if cached is not None:
        if normalize_lang(cached["language_code"]) == translate_to:
            return cached
        return translate_transcript_text(cached, translate_to)

    try:
        api = get_youtube_api()
        transcript_list = api.list(video_id)
        transcript = _find_transcript(transcript_list, language)

        if normalize_lang(transcript.language_code) == translate_to:
            result = _build_result_from_fetched(video_id, transcript.fetch())
            set_cached_source(video_id, language, result)
            return result

        if transcript.is_translatable:
            source = _build_result_from_fetched(video_id, transcript.fetch())
            set_cached_source(video_id, language, source)
            translated = transcript.translate(translate_to)
            return _build_result_from_fetched(video_id, translated.fetch())

        source = _build_result_from_fetched(video_id, transcript.fetch())
        set_cached_source(video_id, language, source)
        return translate_transcript_text(source, translate_to)
    except (IpBlocked, RequestBlocked):
        source = fetch_transcript_ytdlp(video_id, language)
        set_cached_source(video_id, language, source)
        if normalize_lang(source["language_code"]) == translate_to:
            return source
        return translate_transcript_text(source, translate_to)


def get_transcript(
    url_or_id: str,
    language: str | None = None,
    translate_to: str | None = None,
    use_whisper_fallback: bool = True,
) -> dict:
    video_id = extract_video_id(url_or_id)
    if not video_id:
        raise ValueError("Invalid YouTube URL or video ID.")

    try:
        if translate_to:
            return get_transcript_with_translation(video_id, language, translate_to)
        result = fetch_transcript_with_fallback(video_id, language, translate_to=None)
        set_cached_source(video_id, language, result)
        return result
    except (IpBlocked, RequestBlocked) as exc:
        raise ValueError(IP_BLOCK_HELP) from exc
    except (NoTranscriptFound, TranscriptsDisabled):
        if not use_whisper_fallback:
            raise ValueError(
                "No captions available for this video. Enable Whisper fallback or try another video."
            )
        return transcribe_with_whisper(video_id, language=language or translate_to)
    except VideoUnavailable:
        raise ValueError("Video is unavailable or private.")
