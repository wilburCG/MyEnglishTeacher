"""M1 学习闭环：今日队列、SRS 复习、单词听写、统计、收藏。"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, case, delete, func, select

from app.core.checker import check_answer
from app.core.srs import SrsState, due_for, schedule
from app.db import SessionLocal
from app.deps import get_current_user
from app.models import ReviewLog, User, UserWordState, Word

router = APIRouter(prefix="/api/v1")

CN_TZ = timezone(timedelta(hours=8))
DUE_CAP = 200
DICTATION_CAP = 20


def now_cn() -> datetime:
    return datetime.now(CN_TZ)


def _aware(dt: datetime) -> datetime:
    # SQLite 返回 naive datetime（按 UTC 存储），统一补时区
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def day_bounds(now: datetime):
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def word_out(w: Word, state: UserWordState | None = None) -> dict:
    return {
        "id": w.id,
        "headword": w.headword,
        "phonetic": w.phonetic,
        "pos": w.pos,
        "definition_en": w.definition_en,
        "translation": w.translation,
        "level": w.level,
        "unit": w.unit,
        "examples": w.examples or [],
        "favorite": state.is_favorite if state else False,
    }


def _get_word(db, word_id: int) -> Word:
    w = db.get(Word, word_id)
    if w is None:
        raise HTTPException(status_code=404, detail="单词不存在")
    return w


def _get_or_create_state(db, user_id: int, word_id: int) -> UserWordState:
    state = db.scalar(
        select(UserWordState).where(
            and_(
                UserWordState.user_id == user_id,
                UserWordState.word_id == word_id,
            )
        )
    )
    if state is None:
        state = UserWordState(
            user_id=user_id, word_id=word_id, due_at=now_cn()
        )
        db.add(state)
        db.flush()
    return state


def _apply_grade(state: UserWordState, grade: int) -> UserWordState:
    result = schedule(
        SrsState(
            reps=state.reps,
            interval_days=state.interval_days,
            ease_factor=state.ease_factor,
            lapses=state.lapses,
        ),
        grade,
    )
    now = now_cn()
    state.reps = result.reps
    state.interval_days = result.interval_days
    state.ease_factor = result.ease_factor
    state.lapses = result.lapses
    state.due_at = due_for(result.interval_days, now)
    state.last_reviewed_at = now
    return state


class ReviewIn(BaseModel):
    word_id: int
    grade: int = Field(ge=0, le=3)


class DictationIn(BaseModel):
    word_id: int
    answer: str = Field(min_length=1, max_length=128)


class FavoriteIn(BaseModel):
    favorite: bool


@router.get("/learn/queue")
def queue(user: User = Depends(get_current_user)):
    db = SessionLocal()
    now = now_cn()
    day_start, day_end = day_bounds(now)
    try:
        # 今日已学新词数
        introduced_today = db.scalar(
            select(func.count())
            .select_from(UserWordState)
            .where(
                and_(
                    UserWordState.user_id == user.id,
                    UserWordState.introduced_at >= day_start,
                    UserWordState.introduced_at < day_end,
                )
            )
        )
        new_goal_left = max(0, user.daily_new_goal - introduced_today)

        # 到期复习
        due_rows = db.execute(
            select(Word, UserWordState)
            .join(UserWordState, UserWordState.word_id == Word.id)
            .where(
                and_(
                    UserWordState.user_id == user.id,
                    UserWordState.due_at <= now,
                )
            )
            .order_by(UserWordState.due_at.asc())
            .limit(DUE_CAP)
        ).all()
        due = [word_out(w, s) for w, s in due_rows]

        # 新单词
        learned_ids = select(UserWordState.word_id).where(
            UserWordState.user_id == user.id
        )
        order = Word.seq.asc() if user.level == "junior-g7" else (
            case((Word.frq > 0, Word.frq), else_=999999999).asc(),
            Word.seq.asc(),
        )
        new_rows = db.execute(
            select(Word)
            .where(and_(Word.level == user.level, Word.id.not_in(learned_ids)))
            .order_by(*(order if isinstance(order, tuple) else (order,)))
            .limit(new_goal_left)
        ).scalars().all()
        new_words = [word_out(w) for w in new_rows]

        return {
            "due": due,
            "new": new_words,
            "counts": {
                "due": len(due),
                "new": len(new_words),
                "new_goal": user.daily_new_goal,
                "introduced_today": introduced_today,
            },
        }
    finally:
        db.close()


@router.post("/learn/review")
def review(req: ReviewIn, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        word = _get_word(db, req.word_id)
        state = _get_or_create_state(db, user.id, word.id)
        state = _apply_grade(state, req.grade)
        if req.grade == 0:
            state.wrong_count += 1
        db.add(
            ReviewLog(
                user_id=user.id,
                word_id=word.id,
                grade=req.grade,
                kind="card",
                correct=req.grade > 0,
                interval_days=state.interval_days,
            )
        )
        db.commit()
        return {
            "word_id": word.id,
            "interval_days": state.interval_days,
            "due_at": state.due_at.isoformat(),
            "reps": state.reps,
        }
    finally:
        db.close()


@router.get("/learn/dictation-queue")
def dictation_queue(user: User = Depends(get_current_user)):
    """先到期词，不够用今日新词补。"""
    db = SessionLocal()
    now = now_cn()
    try:
        due_rows = db.execute(
            select(Word)
            .join(UserWordState, UserWordState.word_id == Word.id)
            .where(
                and_(
                    UserWordState.user_id == user.id,
                    UserWordState.due_at <= now,
                )
            )
            .order_by(UserWordState.due_at.asc())
            .limit(DICTATION_CAP)
        ).scalars().all()
        words = list(due_rows)
        if len(words) < DICTATION_CAP:
            learned_ids = select(UserWordState.word_id).where(
                UserWordState.user_id == user.id
            )
            fill = db.execute(
                select(Word)
                .where(
                    and_(Word.level == user.level, Word.id.not_in(learned_ids))
                )
                .order_by(Word.seq.asc())
                .limit(DICTATION_CAP - len(words))
            ).scalars().all()
            words.extend(fill)
        return {"words": [word_out(w) for w in words]}
    finally:
        db.close()


@router.post("/learn/dictation")
def dictation_check(req: DictationIn, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        word = _get_word(db, req.word_id)
        result = check_answer(req.answer, word.headword)
        state = _get_or_create_state(db, user.id, word.id)
        grade = 2 if result["correct"] else 0
        state = _apply_grade(state, grade)
        if not result["correct"]:
            state.wrong_count += 1
        db.add(
            ReviewLog(
                user_id=user.id,
                word_id=word.id,
                grade=grade,
                kind="dictation",
                correct=result["correct"],
                interval_days=state.interval_days,
            )
        )
        db.commit()
        result["phonetic"] = word.phonetic
        result["translation"] = word.translation
        result["examples"] = word.examples or []
        return result
    finally:
        db.close()


@router.get("/learn/summary")
def summary(user: User = Depends(get_current_user)):
    db = SessionLocal()
    now = now_cn()
    day_start, day_end = day_bounds(now)
    try:
        states = db.execute(
            select(UserWordState).where(UserWordState.user_id == user.id)
        ).scalars().all()
        learned = len(states)
        mastered = sum(1 for s in states if s.interval_days >= 21)
        due_count = sum(1 for s in states if _aware(s.due_at) <= now)
        favorites = sum(1 for s in states if s.is_favorite)

        today_logs = db.execute(
            select(ReviewLog).where(
                and_(
                    ReviewLog.user_id == user.id,
                    ReviewLog.reviewed_at >= day_start,
                    ReviewLog.reviewed_at < day_end,
                )
            )
        ).scalars().all()
        today_reviews = len(today_logs)
        today_correct = sum(1 for r in today_logs if r.correct)

        # streak：从今天（或昨天）往前连续有记录的天数
        days = set()
        for reviewed in db.execute(
            select(ReviewLog.reviewed_at).where(ReviewLog.user_id == user.id)
        ).scalars():
            if reviewed.tzinfo is None:
                reviewed = reviewed.replace(tzinfo=timezone.utc)
            days.add(reviewed.astimezone(CN_TZ).date())
        streak = 0
        cursor = now.date()
        if cursor not in days:
            cursor -= timedelta(days=1)
        while cursor in days:
            streak += 1
            cursor -= timedelta(days=1)

        return {
            "level": user.level,
            "daily_new_goal": user.daily_new_goal,
            "learned": learned,
            "mastered": mastered,
            "due": due_count,
            "favorites": favorites,
            "streak_days": streak,
            "today_reviews": today_reviews,
            "today_correct": today_correct,
            "today_accuracy": round(today_correct / today_reviews, 3)
            if today_reviews
            else None,
        }
    finally:
        db.close()


@router.post("/words/{word_id}/favorite")
def toggle_favorite(
    word_id: int, req: FavoriteIn, user: User = Depends(get_current_user)
):
    db = SessionLocal()
    try:
        word = _get_word(db, word_id)
        state = _get_or_create_state(db, user.id, word.id)
        state.is_favorite = req.favorite
        db.commit()
        return {"word_id": word_id, "favorite": state.is_favorite}
    finally:
        db.close()


@router.get("/favorites")
def favorites(user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        rows = db.execute(
            select(Word, UserWordState)
            .join(UserWordState, UserWordState.word_id == Word.id)
            .where(
                and_(
                    UserWordState.user_id == user.id,
                    UserWordState.is_favorite.is_(True),
                )
            )
            .order_by(UserWordState.last_reviewed_at.desc().nullslast())
        ).all()
        return {"words": [word_out(w, s) for w, s in rows]}
    finally:
        db.close()
