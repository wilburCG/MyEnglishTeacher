"""M2 内容模块：典型句型 + Friends 台词的列表/详情/收藏 + 管理员 CRUD。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, func, select

from app.db import SessionLocal
from app.deps import get_admin_user, get_current_user
from app.models import (
    ContentFavorite,
    MovieLine,
    SentencePattern,
    User,
)

router = APIRouter(prefix="/api/v1")
admin_router = APIRouter(prefix="/api/v1/admin")

# 级别列表（与前端 levels.ts 对齐）
LEVELS = ["junior-g7", "junior", "senior", "cet4", "cet6", "ielts"]
ITEM_TYPES = {"pattern": SentencePattern, "line": MovieLine}


# ---------- 序列化 ----------

def pattern_out(p: SentencePattern, favorite: bool = False) -> dict:
    return {
        "id": p.id,
        "level": p.level,
        "theme": p.theme,
        "unit": p.unit,
        "template": p.template,
        "func_zh": p.func_zh,
        "grammar_point": p.grammar_point,
        "explanation_zh": p.explanation_zh,
        "examples": p.examples or [],
        "favorite": favorite,
    }


def line_out(l: MovieLine, favorite: bool = False) -> dict:
    return {
        "id": l.id,
        "show": l.show,
        "season": l.season,
        "episode": l.episode,
        "character": l.character,
        "text_en": l.text_en,
        "text_zh": l.text_zh,
        "level": l.level,
        "theme": l.theme,
        "note_zh": l.note_zh,
        "favorite": favorite,
    }


def _favorite_ids(db, user_id: int, item_type: str, ids: list[int]) -> set[int]:
    if not ids:
        return set()
    rows = db.execute(
        select(ContentFavorite.item_id).where(
            and_(
                ContentFavorite.user_id == user_id,
                ContentFavorite.item_type == item_type,
                ContentFavorite.item_id.in_(ids),
            )
        )
    ).scalars().all()
    return set(rows)


# ---------- 句型 ----------

@router.get("/patterns")
def list_patterns(
    level: str | None = None,
    theme: str | None = None,
    include_all_levels: bool = False,
    user: User = Depends(get_current_user),
):
    db = SessionLocal()
    try:
        conds = [SentencePattern.is_published.is_(True)]
        if level:
            if level not in LEVELS:
                raise HTTPException(status_code=400, detail="未知级别")
            conds.append(SentencePattern.level == level)
        elif not include_all_levels:
            conds.append(SentencePattern.level == user.level)
        if theme:
            conds.append(SentencePattern.theme == theme)
        rows = db.execute(
            select(SentencePattern)
            .where(and_(*conds))
            .order_by(SentencePattern.level.asc(), SentencePattern.seq.asc())
        ).scalars().all()
        favs = _favorite_ids(db, user.id, "pattern", [p.id for p in rows])
        return {"patterns": [pattern_out(p, p.id in favs) for p in rows]}
    finally:
        db.close()


@router.get("/patterns/{pid}")
def get_pattern(pid: int, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        p = db.get(SentencePattern, pid)
        if p is None or not p.is_published:
            raise HTTPException(status_code=404, detail="句型不存在")
        favs = _favorite_ids(db, user.id, "pattern", [p.id])
        return pattern_out(p, p.id in favs)
    finally:
        db.close()


# ---------- 台词 ----------

@router.get("/lines")
def list_lines(
    level: str | None = None,
    theme: str | None = None,
    character: str | None = None,
    include_all_levels: bool = False,
    q: str | None = Query(default=None, max_length=32),
    user: User = Depends(get_current_user),
):
    db = SessionLocal()
    try:
        conds = [MovieLine.is_published.is_(True)]
        if level:
            if level not in LEVELS:
                raise HTTPException(status_code=400, detail="未知级别")
            conds.append(MovieLine.level == level)
        elif not include_all_levels:
            conds.append(MovieLine.level == user.level)
        if theme:
            conds.append(MovieLine.theme == theme)
        if character:
            conds.append(MovieLine.character == character)
        if q:
            conds.append(MovieLine.text_en.ilike(f"%{q}%"))
        rows = db.execute(
            select(MovieLine)
            .where(and_(*conds))
            .order_by(
                MovieLine.season.asc().nulls_last(),
                MovieLine.episode.asc().nulls_last(),
                MovieLine.seq.asc(),
            )
        ).scalars().all()
        favs = _favorite_ids(db, user.id, "line", [l.id for l in rows])
        return {"lines": [line_out(l, l.id in favs) for l in rows]}
    finally:
        db.close()


@router.get("/lines/{lid}")
def get_line(lid: int, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        l = db.get(MovieLine, lid)
        if l is None or not l.is_published:
            raise HTTPException(status_code=404, detail="台词不存在")
        favs = _favorite_ids(db, user.id, "line", [l.id])
        return line_out(l, l.id in favs)
    finally:
        db.close()


# ---------- 收藏（句型/台词通用） ----------

class FavoriteToggle(BaseModel):
    item_type: str = Field(pattern="^(pattern|line)$")
    item_id: int
    favorite: bool


@router.post("/content/favorite")
def toggle_content_favorite(
    req: FavoriteToggle, user: User = Depends(get_current_user)
):
    model = ITEM_TYPES[req.item_type]
    db = SessionLocal()
    try:
        obj = db.get(model, req.item_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="内容不存在")
        existing = db.scalar(
            select(ContentFavorite).where(
                and_(
                    ContentFavorite.user_id == user.id,
                    ContentFavorite.item_type == req.item_type,
                    ContentFavorite.item_id == req.item_id,
                )
            )
        )
        if req.favorite and existing is None:
            db.add(
                ContentFavorite(
                    user_id=user.id,
                    item_type=req.item_type,
                    item_id=req.item_id,
                )
            )
        elif not req.favorite and existing is not None:
            db.delete(existing)
        db.commit()
        return {
            "item_type": req.item_type,
            "item_id": req.item_id,
            "favorite": req.favorite,
        }
    finally:
        db.close()


@router.get("/content/favorites")
def content_favorites(
    item_type: str = Query(pattern="^(pattern|line)$"),
    user: User = Depends(get_current_user),
):
    db = SessionLocal()
    try:
        rows = db.execute(
            select(ContentFavorite.item_id)
            .where(
                and_(
                    ContentFavorite.user_id == user.id,
                    ContentFavorite.item_type == item_type,
                )
            )
            .order_by(ContentFavorite.created_at.desc())
        ).scalars().all()
        model = ITEM_TYPES[item_type]
        objs = [db.get(model, i) for i in rows]
        objs = [o for o in objs if o is not None and o.is_published]
        if item_type == "pattern":
            return {"patterns": [pattern_out(o, True) for o in objs]}
        return {"lines": [line_out(o, True) for o in objs]}
    finally:
        db.close()


# ---------- 管理员 CRUD ----------

class PatternIn(BaseModel):
    level: str
    theme: str = Field(min_length=1, max_length=32)
    unit: str | None = Field(default=None, max_length=32)
    seq: int = 0
    template: str = Field(min_length=1, max_length=256)
    func_zh: str = Field(min_length=1, max_length=256)
    grammar_point: str | None = Field(default=None, max_length=128)
    explanation_zh: str | None = None
    examples: list[dict] = Field(default_factory=list)
    is_published: bool = True


class LineIn(BaseModel):
    show: str = Field(default="Friends", max_length=64)
    season: int | None = Field(default=None, ge=1, le=30)
    episode: int | None = Field(default=None, ge=1, le=100)
    character: str = Field(min_length=1, max_length=64)
    text_en: str = Field(min_length=1)
    text_zh: str = Field(min_length=1)
    level: str
    theme: str | None = Field(default=None, max_length=32)
    note_zh: str | None = None
    seq: int = 0
    is_published: bool = True


def _validate_level(level: str):
    if level not in LEVELS:
        raise HTTPException(status_code=400, detail="未知级别")


@admin_router.post("/patterns")
def admin_create_pattern(
    req: PatternIn, admin: User = Depends(get_admin_user)
):
    _validate_level(req.level)
    db = SessionLocal()
    try:
        p = SentencePattern(**req.model_dump())
        db.add(p)
        db.commit()
        db.refresh(p)
        return pattern_out(p)
    finally:
        db.close()


@admin_router.patch("/patterns/{pid}")
def admin_update_pattern(
    pid: int, req: PatternIn, admin: User = Depends(get_admin_user)
):
    _validate_level(req.level)
    db = SessionLocal()
    try:
        p = db.get(SentencePattern, pid)
        if p is None:
            raise HTTPException(status_code=404, detail="句型不存在")
        for k, v in req.model_dump().items():
            setattr(p, k, v)
        db.commit()
        db.refresh(p)
        return pattern_out(p)
    finally:
        db.close()


@admin_router.delete("/patterns/{pid}")
def admin_delete_pattern(pid: int, admin: User = Depends(get_admin_user)):
    db = SessionLocal()
    try:
        p = db.get(SentencePattern, pid)
        if p is None:
            raise HTTPException(status_code=404, detail="句型不存在")
        db.execute(
            delete(ContentFavorite).where(
                and_(
                    ContentFavorite.item_type == "pattern",
                    ContentFavorite.item_id == pid,
                )
            )
        )
        db.delete(p)
        db.commit()
        return {"deleted": pid}
    finally:
        db.close()


@admin_router.post("/lines")
def admin_create_line(req: LineIn, admin: User = Depends(get_admin_user)):
    _validate_level(req.level)
    db = SessionLocal()
    try:
        l = MovieLine(**req.model_dump())
        db.add(l)
        db.commit()
        db.refresh(l)
        return line_out(l)
    finally:
        db.close()


@admin_router.patch("/lines/{lid}")
def admin_update_line(
    lid: int, req: LineIn, admin: User = Depends(get_admin_user)
):
    _validate_level(req.level)
    db = SessionLocal()
    try:
        l = db.get(MovieLine, lid)
        if l is None:
            raise HTTPException(status_code=404, detail="台词不存在")
        for k, v in req.model_dump().items():
            setattr(l, k, v)
        db.commit()
        db.refresh(l)
        return line_out(l)
    finally:
        db.close()


@admin_router.delete("/lines/{lid}")
def admin_delete_line(lid: int, admin: User = Depends(get_admin_user)):
    db = SessionLocal()
    try:
        l = db.get(MovieLine, lid)
        if l is None:
            raise HTTPException(status_code=404, detail="台词不存在")
        db.execute(
            delete(ContentFavorite).where(
                and_(
                    ContentFavorite.item_type == "line",
                    ContentFavorite.item_id == lid,
                )
            )
        )
        db.delete(l)
        db.commit()
        return {"deleted": lid}
    finally:
        db.close()
