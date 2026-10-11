"""M4 句子听写：材料队列、听写音频、确定性判题、错句复习闭环。"""
from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select

from app.core import audio
from app.core.sentence_checker import check_sentence
from app.db import SessionLocal
from app.deps import get_current_user
from app.models import (
    DictationAttempt,
    MovieLine,
    ReviewItem,
    SentencePattern,
    User,
    UserWordState,
    Word,
)

router = APIRouter(prefix="/api/v1/dictation", tags=["dictation"])

QUEUE_CAP = 10
REVIEW_STREAK_TARGET = 2
REVIEW_INTERVAL_MIN = 10

SOURCES = ("auto", "review", "patterns", "lines", "words")


def now_cn():
    from app.learn_api import now_cn as _n
    return _n()


def _split_word_example(raw: str) -> tuple[str, str]:
    """'Hello! Nice to meet you.（你好。）' -> ('Hello! Nice to meet you.', '你好。')"""
    m = re.match(r"^(.*?)[（(]\s*(.*?)\s*[)）]\s*$", raw.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return raw.strip(), ""


def _pattern_items(db, level: str, limit: int):
    rows = db.scalars(
        select(SentencePattern)
        .where(and_(SentencePattern.is_published.is_(True), SentencePattern.level == level))
        .order_by(func.random())
        .limit(limit)
    ).all()
    items = []
    for p in rows:
        for i, ex in enumerate(p.examples or []):
            en = ex.get("en") if isinstance(ex, dict) else None
            if en:
                items.append({
                    "source_type": "pattern",
                    "source_id": p.id,
                    "sentence_index": i,
                    "target": en.strip(),
                    "zh_hint": (ex.get("zh") if isinstance(ex, dict) else "") or "",
                    "source_title": p.template,
                })
    return items


def _line_items(db, level: str, limit: int):
    rows = db.scalars(
        select(MovieLine)
        .where(and_(MovieLine.is_published.is_(True), MovieLine.level == level))
        .order_by(func.random())
        .limit(limit)
    ).all()
    return [{
        "source_type": "line",
        "source_id": l.id,
        "sentence_index": 0,
        "target": l.text_en.strip(),
        "zh_hint": l.text_zh or "",
        "source_title": f"Friends · {l.character}",
    } for l in rows]


def _word_items(db, user: User, limit: int):
    # 优先用户学过的词，不够时补本级词
    learned = db.scalars(
        select(Word)
        .where(Word.level == user.level)
        .join(UserWordState, and_(
            UserWordState.word_id == Word.id,
            UserWordState.user_id == user.id,
        ))
        .where(Word.examples.isnot(None))
        .order_by(func.random())
        .limit(limit)
    ).all()
    pool = list(learned)
    if len(pool) < limit:
        have = {w.id for w in pool}
        extra = db.scalars(
            select(Word)
            .where(and_(
                Word.level == user.level,
                Word.examples.isnot(None),
                Word.id.notin_(have) if have else True,
            ))
            .order_by(func.random())
            .limit(limit - len(pool))
        ).all()
        pool.extend(extra)

    items = []
    for w in pool:
        for i, raw in enumerate(w.examples or []):
            if isinstance(raw, dict):
                en, zh = (raw.get("en") or "").strip(), raw.get("zh") or ""
            else:
                en, zh = _split_word_example(str(raw))
            if en:
                items.append({
                    "source_type": "word_example",
                    "source_id": w.id,
                    "sentence_index": i,
                    "target": en,
                    "zh_hint": zh,
                    "source_title": w.headword,
                })
    return items


def _review_items(db, user: User, limit: int):
    now = now_cn()
    rows = db.scalars(
        select(ReviewItem)
        .where(and_(
            ReviewItem.user_id == user.id,
            ReviewItem.source_type == "dictation_error",
            ReviewItem.is_resolved.is_(False),
            or_(ReviewItem.due_at.is_(None), ReviewItem.due_at <= now),
        ))
        .order_by(ReviewItem.due_at.asc().nullslast(), func.random())
        .limit(limit)
    ).all()
    return [{
        "source_type": "review",
        "source_id": r.id,
        "sentence_index": 0,
        "target": r.original,
        "zh_hint": r.explanation_zh or "",
        "source_title": r.title or "错句复习",
        "streak": r.streak,
    } for r in rows]


def _material(db, user: User, source_type: str, source_id: int,
              sentence_index: int) -> dict[str, Any]:
    if source_type == "pattern":
        p = db.get(SentencePattern, source_id)
        if not p or not p.is_published or not (p.examples or []):
            raise HTTPException(status_code=404, detail="材料不存在")
        ex = p.examples[sentence_index]
        return {
            "target": ex["en"].strip(),
            "zh_hint": ex.get("zh", ""),
            "source_title": p.template,
        }
    if source_type == "line":
        l = db.get(MovieLine, source_id)
        if not l or not l.is_published:
            raise HTTPException(status_code=404, detail="材料不存在")
        if sentence_index != 0:
            raise HTTPException(status_code=400, detail="台词材料没有句子序号")
        return {"target": l.text_en.strip(), "zh_hint": l.text_zh or "",
                "source_title": f"Friends · {l.character}"}
    if source_type == "word_example":
        w = db.get(Word, source_id)
        if not w or not w.examples:
            raise HTTPException(status_code=404, detail="材料不存在")
        raw = w.examples[sentence_index]
        if isinstance(raw, dict):
            return {"target": raw["en"].strip(), "zh_hint": raw.get("zh", ""),
                    "source_title": w.headword}
        en, zh = _split_word_example(str(raw))
        return {"target": en, "zh_hint": zh, "source_title": w.headword}
    if source_type == "review":
        r = db.get(ReviewItem, source_id)
        if not r or r.user_id != user.id or r.source_type != "dictation_error":
            raise HTTPException(status_code=404, detail="复习项不存在")
        return {"target": r.original, "zh_hint": r.explanation_zh or "",
                "source_title": r.title or "错句复习"}
    raise HTTPException(status_code=400, detail="未知材料来源")


def _public_item(item: dict) -> dict:
    return {
        "item_id": f"{item['source_type']}:{item['source_id']}:{item['sentence_index']}",
        "source_type": item["source_type"],
        "source_id": item["source_id"],
        "sentence_index": item["sentence_index"],
        "zh_hint": item["zh_hint"],
        "source_title": item["source_title"],
        "word_count": len(item["target"].split()),
        "streak": item.get("streak"),
    }


@router.get("/sentence-queue")
def sentence_queue(
    source: str = Query("auto", pattern="^(auto|review|patterns|lines|words)$"),
    limit: int = Query(QUEUE_CAP, ge=1, le=20),
    user: User = Depends(get_current_user),
):
    db = SessionLocal()
    try:
        if source == "review":
            items = _review_items(db, user, limit)
        elif source == "patterns":
            items = _pattern_items(db, user.level, limit)
        elif source == "lines":
            items = _line_items(db, user.level, limit)
        elif source == "words":
            items = _word_items(db, user, limit)
        else:  # auto：错句优先，其余从台词/句型补
            items = _review_items(db, user, limit)
            if len(items) < limit:
                fill_lines = _line_items(db, user.level, limit - len(items))
                items.extend(fill_lines[: limit - len(items)])
            if len(items) < limit:
                n = limit - len(items)
                for it in _pattern_items(db, user.level, n):
                    if len(items) >= limit:
                        break
                    items.append(it)

        # 已掌握的复习项不应出现在内容队列（review 队列自身只取未掌握）
        return {"items": [_public_item(x) for x in items[:limit]], "source": source}
    finally:
        db.close()


@router.get("/audio")
def dictation_audio(
    source_type: str = Query(...),
    source_id: int = Query(...),
    sentence_index: int = Query(0, ge=0),
    speed: str = Query("normal", pattern="^(normal|slow)$"),
    user: User = Depends(get_current_user),
):
    db = SessionLocal()
    try:
        mat = _material(db, user, source_type, source_id, sentence_index)
    finally:
        db.close()
    path = audio.sentence_audio_path(mat["target"], "us", speed)
    if path is None:
        raise HTTPException(status_code=502, detail="发音服务暂不可用")
    return FileResponse(path, media_type="audio/mpeg")


class SentenceCheckIn(BaseModel):
    source_type: str
    source_id: int
    sentence_index: int = Field(0, ge=0)
    answer: str = Field(min_length=1, max_length=600)
    hint_count: int = Field(0, ge=0, le=20)


def _find_review_item(db, user_id: int, source_type: str, source_id: int,
                      sentence_index: int, target: str):
    return db.scalar(
        select(ReviewItem).where(and_(
            ReviewItem.user_id == user_id,
            ReviewItem.source_type == "dictation_error",
            ReviewItem.source_conversation_id == source_id,
            ReviewItem.source_message_id == sentence_index,
            ReviewItem.original == target,
        ))
    )


@router.post("/sentence-check")
def sentence_check(req: SentenceCheckIn, user: User = Depends(get_current_user)):
    if req.source_type not in ("pattern", "line", "word_example", "review"):
        raise HTTPException(status_code=400, detail="未知材料来源")
    db = SessionLocal()
    try:
        # review 来源：source_id 是 review_item.id，先拿到它对应的真实材料键
        material_key = None
        if req.source_type == "review":
            r = db.get(ReviewItem, req.source_id)
            if not r or r.user_id != user.id or r.source_type != "dictation_error":
                raise HTTPException(status_code=404, detail="复习项不存在")
            material_key = ("dictation_error", r.source_conversation_id or 0,
                            r.source_message_id or 0)

        mat = _material(db, user, req.source_type, req.source_id, req.sentence_index)
        target = mat["target"]
        result = check_sentence(req.answer, target)

        # 复习本联动（统一用真实材料键）
        if material_key is None:
            material_key = ("dictation_error", req.source_id, req.sentence_index)
        _, ref_id, ref_index = material_key
        item = _find_review_item(db, user.id, "dictation_error",
                                 ref_id, ref_index, target)

        review_action = "none"
        if not result["correct"]:
            if item is None:
                item = ReviewItem(
                    user_id=user.id,
                    source_type="dictation_error",
                    source_conversation_id=ref_id,
                    source_message_id=ref_index,
                    item_kind="sentence",
                    title=mat["source_title"][:256],
                    original=target,
                    corrected=target,
                    explanation_zh=mat.get("zh_hint") or None,
                    context_sentence=target,
                    wrong_count=0,
                    streak=0,
                    due_at=now_cn(),
                )
                db.add(item)
            item.wrong_count += 1
            item.streak = 0
            item.is_resolved = False
            item.due_at = now_cn()
            review_action = "added"
            if item.id and req.source_type != "review":
                review_action = "added"
        elif item is not None and not item.is_resolved:
            item.streak += 1
            if item.streak >= REVIEW_STREAK_TARGET:
                item.is_resolved = True
                item.due_at = None
                review_action = "mastered"
            else:
                item.due_at = now_cn() + timedelta(minutes=REVIEW_INTERVAL_MIN)
                review_action = "streak"

        attempt = DictationAttempt(
            user_id=user.id,
            source_type=req.source_type,
            source_id=req.source_id,
            sentence_index=req.sentence_index,
            target_text=target,
            answer_text=req.answer[:600],
            result=result,
            correct=result["correct"],
            score=result["score"],
            hint_count=req.hint_count,
        )
        db.add(attempt)
        db.commit()

        return {
            **result,
            "zh_hint": mat.get("zh_hint", ""),
            "source_title": mat.get("source_title", ""),
            "review_action": review_action,
            "review_streak": item.streak if item else 0,
        }
    finally:
        db.close()
