"""M2 内容导入：七年级句型 + Friends 台词（幂等 upsert）。

用法（容器内）：
  python -m scripts.import_content
"""
import json
import os

from sqlalchemy import select

from app.db import SessionLocal
from app.models import MovieLine, SentencePattern

SEED_DIR = os.path.join(os.path.dirname(__file__), "seed")


def import_patterns(db) -> tuple[int, int]:
    data = json.load(
        open(os.path.join(SEED_DIR, "patterns_g7.json"), encoding="utf-8")
    )
    existing = {p.template: p for p in db.scalars(select(SentencePattern)).all()}
    created = updated = 0
    for item in data:
        obj = existing.get(item["template"])
        if obj is None:
            obj = SentencePattern(template=item["template"])
            db.add(obj)
            created += 1
        else:
            updated += 1
        for key in (
            "level",
            "theme",
            "unit",
            "seq",
            "func_zh",
            "grammar_point",
            "explanation_zh",
            "examples",
        ):
            setattr(obj, key, item.get(key))
        obj.is_published = True
    db.flush()
    return created, updated


def import_lines(db) -> tuple[int, int]:
    data = json.load(
        open(os.path.join(SEED_DIR, "friends_lines.json"), encoding="utf-8")
    )
    existing = {l.text_en: l for l in db.scalars(select(MovieLine)).all()}
    created = updated = 0
    for item in data:
        obj = existing.get(item["text_en"])
        if obj is None:
            obj = MovieLine(text_en=item["text_en"])
            db.add(obj)
            created += 1
        else:
            updated += 1
        for key in (
            "show",
            "season",
            "episode",
            "character",
            "text_zh",
            "level",
            "theme",
            "note_zh",
            "seq",
        ):
            setattr(obj, key, item.get(key))
        obj.is_published = True
    db.flush()
    return created, updated


def main():
    db = SessionLocal()
    try:
        p = import_patterns(db)
        l = import_lines(db)
        db.commit()
        pc = db.query(SentencePattern).count()
        lc = db.query(MovieLine).count()
        print(
            f"patterns: created={p[0]} updated={p[1]} total={pc}\n"
            f"lines:    created={l[0]} updated={l[1]} total={lc}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
