from __future__ import annotations

SOURCE_CACHE: dict[tuple[str, str], dict] = {}
TRANSLATION_CACHE: dict[tuple[str, str, str], str] = {}


def cache_key_video(video_id: str, language: str | None) -> tuple[str, str]:
    return (video_id, language or "")


def get_cached_source(video_id: str, language: str | None) -> dict | None:
    return SOURCE_CACHE.get(cache_key_video(video_id, language))


def set_cached_source(video_id: str, language: str | None, result: dict) -> None:
    SOURCE_CACHE[cache_key_video(video_id, language)] = result


def get_cached_translation(text: str, source_lang: str, target_lang: str) -> str | None:
    return TRANSLATION_CACHE.get((text, source_lang, target_lang))


def set_cached_translation(text: str, source_lang: str, target_lang: str, translated: str) -> None:
    TRANSLATION_CACHE[(text, source_lang, target_lang)] = translated
