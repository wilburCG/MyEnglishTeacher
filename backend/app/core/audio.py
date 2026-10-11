"""TTS 发音：单词走有道真人发音（失败回退 edge-tts），句子走 edge-tts，全部落盘缓存。"""
import asyncio
import hashlib
from pathlib import Path

import edge_tts
import httpx

from app.config import get_settings

settings = get_settings()
AUDIO_DIR = Path(settings.media_dir) / "audio"
(AUDIO_DIR / "word").mkdir(parents=True, exist_ok=True)
(AUDIO_DIR / "sentence").mkdir(parents=True, exist_ok=True)

_VOICES = {
    "us": ("1", "en-US-AriaNeural"),
    "uk": ("2", "en-GB-SoniaNeural"),
}


async def _edge_to_file(text: str, voice: str, path: Path) -> bool:
    try:
        await edge_tts.Communicate(text, voice).save(str(path))
        return path.exists() and path.stat().st_size > 100
    except Exception:
        if path.exists():
            path.unlink()
        return False


def _edge_sync(text: str, voice: str, path: Path) -> bool:
    return asyncio.run(_edge_to_file(text, voice, path))


def word_audio_path(headword: str, accent: str = "us") -> Path | None:
    yd_type, edge_voice = _VOICES.get(accent, _VOICES["us"])
    safe = hashlib.sha1(headword.encode()).hexdigest()[:16]
    cache = AUDIO_DIR / "word" / f"{safe}_{accent}.mp3"
    if cache.exists() and cache.stat().st_size > 100:
        return cache
    try:
        r = httpx.get(
            "https://dict.youdao.com/dictvoice",
            params={"audio": headword, "type": yd_type},
            timeout=12,
            follow_redirects=True,
        )
        if r.status_code == 200 and r.headers.get("content-type", "").startswith(
            "audio"
        ) and len(r.content) > 500:
            cache.write_bytes(r.content)
            return cache
    except httpx.HTTPError:
        pass
    if _edge_sync(headword, edge_voice, cache):
        return cache
    return None


def sentence_audio_path(text: str, accent: str = "us") -> Path | None:
    text = text.strip()[:200]
    _, edge_voice = _VOICES.get(accent, _VOICES["us"])
    key = hashlib.sha1((text + accent).encode()).hexdigest()
    cache = AUDIO_DIR / "sentence" / f"{key}.mp3"
    if cache.exists() and cache.stat().st_size > 100:
        return cache
    if _edge_sync(text, edge_voice, cache):
        return cache
    return None
