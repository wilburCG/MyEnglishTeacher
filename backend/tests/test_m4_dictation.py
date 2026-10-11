from pathlib import Path

import pytest

from app.db import SessionLocal
from app.models import (
    DictationAttempt,
    MovieLine,
    ReviewItem,
    SentencePattern,
    Word,
)


@pytest.fixture(scope="module")
def token(client):
    r = client.post(
        "/api/v1/auth/phone",
        json={"phone": "13577778888", "display_name": "M4听写同学"},
    )
    assert r.status_code == 200
    return r.json()["token"]


@pytest.fixture(scope="module", autouse=True)
def seed_materials(client):
    db = SessionLocal()
    if db.query(SentencePattern).filter(SentencePattern.template == "M4 test").count() == 0:
        db.add(SentencePattern(
            level="junior-g7",
            theme="校园生活",
            seq=999,
            template="M4 test",
            func_zh="测试",
            examples=[
                {"en": "I go to school by bus.", "zh": "我坐公交上学。"},
            ],
        ))
    if db.query(MovieLine).filter(MovieLine.text_en == "M4 line test.").count() == 0:
        db.add(MovieLine(
            show="Friends", season=9, episode=9, character="Tester",
            text_en="M4 line test.", text_zh="测试台词。",
            level="junior-g7", theme="校园生活", seq=999,
        ))
    db.commit()
    db.close()
    yield


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


def _pattern_id():
    db = SessionLocal()
    p = db.query(SentencePattern).filter_by(template="M4 test").one()
    pid = p.id
    db.close()
    return pid


def test_pattern_queue_and_audio(client, h, monkeypatch):
    pid = _pattern_id()
    r = client.get("/api/v1/dictation/sentence-queue?source=patterns&limit=10", headers=h)
    assert r.status_code == 200
    items = r.json()["items"]
    assert items
    item = next(x for x in items if x["source_id"] == pid)
    assert item["word_count"] == 6
    # 队列不回传原文，防止“偷看”
    assert "target" not in item

    fake = Path("/tmp/met-m4-test.mp3")
    fake.write_bytes(b"ID3fake-audio")
    monkeypatch.setattr(
        "app.dictation_api.audio.sentence_audio_path",
        lambda text, accent="us", speed="normal": fake,
    )
    r = client.get(
        "/api/v1/dictation/audio",
        params={"source_type": "pattern", "source_id": pid,
                "sentence_index": 0, "speed": "slow"},
        headers=h,
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"


def test_wrong_creates_review_item_then_two_corrects_master(client, h):
    pid = _pattern_id()
    body = {
        "source_type": "pattern",
        "source_id": pid,
        "sentence_index": 0,
        "hint_count": 1,
    }

    # 第一次：错 → 进复习本
    r = client.post("/api/v1/dictation/sentence-check", headers=h,
                    json={**body, "answer": "I go to school by car."})
    assert r.status_code == 200
    data = r.json()
    assert data["correct"] is False
    assert data["review_action"] == "added"
    assert data["target"] == "i go to school by bus"

    db = SessionLocal()
    item = db.query(ReviewItem).filter(
        ReviewItem.source_type == "dictation_error",
        ReviewItem.source_conversation_id == pid,
    ).one()
    item_id = item.id
    assert item.streak == 0 and item.is_resolved is False
    db.close()

    # 复习队列能取到
    r = client.get("/api/v1/dictation/sentence-queue?source=review", headers=h)
    assert any(x["source_id"] == item_id for x in r.json()["items"])

    # 第一次对：streak=1，未掌握
    r = client.post("/api/v1/dictation/sentence-check", headers=h,
                    json={"source_type": "pattern", "source_id": pid,
                          "sentence_index": 0, "answer": "I go to school by bus."})
    assert r.json()["review_action"] == "streak"
    assert r.json()["review_streak"] == 1

    # 通过复习入口再对一次：掌握
    r = client.post("/api/v1/dictation/sentence-check", headers=h,
                    json={"source_type": "review", "source_id": item_id,
                          "answer": "I go to school by bus."})
    assert r.json()["review_action"] == "mastered"
    assert r.json()["review_streak"] == 2

    r = client.get("/api/v1/dictation/sentence-queue?source=review", headers=h)
    assert all(x["source_id"] != item_id for x in r.json()["items"])


def test_correct_fresh_material_creates_no_review_item(client, h):
    db = SessionLocal()
    line = db.query(MovieLine).filter_by(text_en="M4 line test.").one()
    lid = line.id
    before = db.query(ReviewItem).count()
    db.close()

    r = client.post("/api/v1/dictation/sentence-check", headers=h, json={
        "source_type": "line", "source_id": lid, "answer": "M4 line test.",
    })
    assert r.json()["correct"] is True
    assert r.json()["review_action"] == "none"

    db = SessionLocal()
    assert db.query(ReviewItem).count() == before
    assert db.query(DictationAttempt).filter_by(correct=True).count() >= 1
    db.close()


def test_review_queue_requires_auth(client):
    assert client.get("/api/v1/dictation/sentence-queue").status_code == 401
