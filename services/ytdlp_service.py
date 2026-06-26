import re
import tempfile
from pathlib import Path

def ytdlp_options(**extra) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    return {**opts, **extra}


def parse_vtt_file(path: Path) -> tuple[str, list[dict]]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    text_parts: list[str] = []
    snippets: list[dict] = []
    seen_text: set[str] = set()

    for block in re.split(r"\n\n+", raw):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or lines[0].startswith("WEBVTT") or lines[0].startswith("NOTE"):
            continue

        time_idx = 0
        if "-->" not in lines[0] and len(lines) > 1 and "-->" in lines[1]:
            time_idx = 1

        if "-->" not in lines[time_idx]:
            continue

        start = _parse_vtt_timestamp(lines[time_idx].split("-->")[0].strip())
        text = " ".join(
            re.sub(r"<[^>]+>", "", line)
            for line in lines[time_idx + 1 :]
        ).strip()
        if not text or text in seen_text:
            continue
        seen_text.add(text)
        text_parts.append(text)
        snippets.append({"text": text, "start": start, "duration": 0.0})

    return " ".join(text_parts), snippets


def _parse_vtt_timestamp(value: str) -> float:
    parts = value.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds.replace(",", "."))
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds.replace(",", "."))
    return 0.0


def _pick_lang_file(tmp_dir: Path, video_id: str, language: str | None) -> Path | None:
    candidates = sorted(tmp_dir.glob(f"{video_id}*.vtt"))
    if not candidates:
        candidates = sorted(tmp_dir.glob("*.vtt"))
    if not candidates:
        return None

    if language:
        for path in candidates:
            if f".{language}." in path.name or path.name.endswith(f".{language}.vtt"):
                return path

    for path in candidates:
        if ".hi." in path.name:
            return path
    for path in candidates:
        if ".en." in path.name:
            return path
    return candidates[0]


def list_languages_ytdlp(video_id: str) -> list[dict]:
    import yt_dlp

    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = ytdlp_options(skip_download=True)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    languages: list[dict] = []
    seen: set[str] = set()

    for lang, _formats in info.get("subtitles", {}).items():
        if lang in seen:
            continue
        seen.add(lang)
        languages.append(
            {
                "code": lang,
                "name": lang,
                "is_generated": False,
                "is_translatable": False,
            }
        )

    for lang, _formats in info.get("automatic_captions", {}).items():
        if lang in seen:
            continue
        seen.add(lang)
        languages.append(
            {
                "code": lang,
                "name": f"{lang} (auto-generated)",
                "is_generated": True,
                "is_translatable": False,
            }
        )

    return languages


def fetch_transcript_ytdlp(video_id: str, language: str | None = None) -> dict:
    import yt_dlp

    url = f"https://www.youtube.com/watch?v={video_id}"
    preferred_langs = [language] if language else ["hi", "en"]

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ydl_opts = ytdlp_options(
            skip_download=True,
            writesubtitles=True,
            writeautomaticsub=True,
            subtitleslangs=preferred_langs,
            subtitlesformat="vtt/best",
            outtmpl=str(tmp_path / "%(id)s"),
        )

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        vtt_file = _pick_lang_file(tmp_path, video_id, language)
        if not vtt_file:
            raise ValueError("No subtitle file found via yt-dlp.")

        text, snippets = parse_vtt_file(vtt_file)
        lang_code = language or _lang_from_filename(vtt_file.name) or "unknown"

        return {
            "video_id": video_id,
            "source": "yt_dlp_captions",
            "language": lang_code,
            "language_code": lang_code,
            "is_generated": ".auto" in vtt_file.name or lang_code.endswith("-orig"),
            "text": text,
            "snippets": snippets,
        }


def _lang_from_filename(name: str) -> str | None:
    match = re.search(r"\.([a-z]{2}(?:-[A-Za-z]+)?)\.vtt$", name)
    return match.group(1) if match else None
