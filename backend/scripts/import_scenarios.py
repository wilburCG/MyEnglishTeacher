"""导入 AI 对话场景卡。幂等：按 level + title_en 更新。"""
from __future__ import annotations

import json
from pathlib import Path

from app.db import SessionLocal
from app.models import Scenario

SEED = Path(__file__).parent / "seed" / "scenarios_g7.json"


def import_scenarios(path: Path = SEED) -> None:
    rows = json.loads(path.read_text(encoding="utf-8"))
    db = SessionLocal()
    try:
        for row in rows:
            obj = db.query(Scenario).filter_by(
                level=row["level"], title_en=row["title_en"]
            ).one_or_none()
            if obj is None:
                obj = Scenario(level=row["level"], title_en=row["title_en"])
                db.add(obj)
            for key in (
                "theme",
                "title_zh",
                "description_zh",
                "teacher_persona",
                "goal",
                "opening_line",
                "recommended_words",
                "difficulty",
                "seq",
            ):
                setattr(obj, key, row[key])
            obj.is_published = True
        db.commit()
        print(f"imported {len(rows)} scenarios")
    finally:
        db.close()


if __name__ == "__main__":
    import_scenarios()
