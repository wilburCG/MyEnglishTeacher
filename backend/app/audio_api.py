from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from app.core import audio
from app.deps import get_current_user
from app.db import SessionLocal
from app.models import Word

router = APIRouter(prefix="/api/v1/audio", tags=["audio"])


@router.get("/word/{word_id}")
def word_audio(
    word_id: int,
    accent: str = Query("us", pattern="^(us|uk)$"),
    user=Depends(get_current_user),
):
    db = SessionLocal()
    try:
        word = db.get(Word, word_id)
        if word is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="单词不存在")
    finally:
        db.close()
    path = audio.word_audio_path(word.headword, accent)
    if path is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=502, detail="发音服务暂不可用")
    return FileResponse(path, media_type="audio/mpeg")


@router.get("/sentence")
def sentence_audio(
    text: str = Query(min_length=1, max_length=200),
    accent: str = Query("us", pattern="^(us|uk)$"),
    user=Depends(get_current_user),
):
    path = audio.sentence_audio_path(text, accent)
    if path is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=502, detail="发音服务暂不可用")
    return FileResponse(path, media_type="audio/mpeg")
