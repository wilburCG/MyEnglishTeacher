import os
import sys

# 必须在任何 app.* 导入前完成：测试一律走临时 sqlite，不碰 Postgres
os.environ["DATABASE_URL"] = "sqlite:///./test_met.db"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["MEDIA_DIR"] = "/tmp/met-test-media"

if os.path.exists("./test_met.db"):
    os.remove("./test_met.db")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Word


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        db = SessionLocal()
        if db.query(Word).count() == 0:
            db.add_all(
                [
                    Word(
                        headword="abandon",
                        phonetic="/əˈbændən/",
                        translation="v. 放弃；抛弃",
                        level="junior-g7",
                        seq=1,
                    ),
                    Word(
                        headword="hello",
                        phonetic="/həˈləʊ/",
                        translation="interj. 喂；你好",
                        level="junior-g7",
                        seq=2,
                    ),
                ]
            )
            db.commit()
        db.close()
        yield c

