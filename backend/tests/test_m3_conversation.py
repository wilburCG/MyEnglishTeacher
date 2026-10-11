import pytest

from app.db import SessionLocal
from app.models import Scenario


@pytest.fixture(scope="module")
def token(client):
    r = client.post(
        "/api/v1/auth/phone",
        json={"phone": "13533334444", "display_name": "M3对话同学"},
    )
    assert r.status_code == 200
    return r.json()["token"]


@pytest.fixture(scope="module", autouse=True)
def seed_scenario(client):
    db = SessionLocal()
    if db.query(Scenario).count() == 0:
        db.add(
            Scenario(
                level="junior-g7",
                theme="校园生活",
                title_en="Meet a New Classmate",
                title_zh="认识新同学",
                description_zh="测试场景",
                teacher_persona="Friendly classmate",
                goal="Greet and introduce yourself",
                opening_line="Hi! What's your name?",
                recommended_words=["hi", "name"],
                difficulty=1,
                seq=1,
            )
        )
        db.commit()
    sid = db.query(Scenario).first().id
    db.close()
    return sid


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


def test_scenario_start_and_turn(client, h, seed_scenario, monkeypatch):
    async def fake_chat_json(**kwargs):
        assert kwargs["user_text"]
        return {
            "has_error": True,
            "corrections": [
                {
                    "original": "go",
                    "corrected": "went",
                    "kind": "tense",
                    "explanation_zh": "yesterday 用过去式",
                }
            ],
            "teacher_reply": "Nice! What did you do after school?",
            "better_version": "I went to school yesterday.",
            "hint_zh": "",
            "model_validated": True,
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "raw_model": "fake-model",
        }

    monkeypatch.setattr("app.conversation_api.chat_json", fake_chat_json)

    r = client.get("/api/v1/scenarios", headers=h)
    assert r.status_code == 200
    assert r.json()["scenarios"][0]["opening_line"] == "Hi! What's your name?"

    r = client.post(
        "/api/v1/conversations", headers=h, json={"scenario_id": seed_scenario}
    )
    assert r.status_code == 200
    cid = r.json()["id"]

    r = client.get(f"/api/v1/conversations/{cid}", headers=h)
    assert r.status_code == 200
    assert r.json()["messages"][0]["role"] == "assistant"

    r = client.post(
        f"/api/v1/conversations/{cid}/messages",
        headers=h,
        json={"text": "I go to school yesterday."},
    )
    assert r.status_code == 200
    turn = r.json()["turn"]
    assert turn["user_message"]["has_error"] is True
    assert turn["user_message"]["corrections"][0]["kind"] == "tense"
    assert "What did you do" in turn["assistant_message"]["content"]

    r = client.get(f"/api/v1/conversations/{cid}", headers=h)
    assert len(r.json()["messages"]) == 3


def test_review_items_and_report(client, h, seed_scenario, monkeypatch):
    async def fake_chat_json(**kwargs):
        return {
            "has_error": False,
            "corrections": [],
            "teacher_reply": "Great! What is your favorite class?",
            "better_version": "",
            "hint_zh": "",
            "model_validated": True,
            "usage": {},
            "raw_model": "fake-model",
        }

    async def broken_report(**kwargs):
        raise RuntimeError("do not call real LLM in tests")

    monkeypatch.setattr("app.conversation_api.chat_json", fake_chat_json)
    monkeypatch.setattr(
        "app.conversation_api.generate_conversation_report", broken_report
    )

    convs = client.get("/api/v1/conversations", headers=h).json()["conversations"]
    cid = convs[0]["id"]

    r = client.post(
        f"/api/v1/conversations/{cid}/review-items",
        headers=h,
        json={"save_all": True},
    )
    assert r.status_code == 200
    assert r.json()["count"] == 1

    # 幂等保存
    r2 = client.post(
        f"/api/v1/conversations/{cid}/review-items",
        headers=h,
        json={"save_all": True},
    )
    assert r2.json()["count"] == 1
    item_id = r2.json()["saved"][0]["id"]

    r = client.get("/api/v1/review-items", headers=h)
    assert r.json()["items"][0]["original"] == "go"

    r = client.patch(f"/api/v1/review-items/{item_id}", headers=h, json={"is_resolved": True})
    assert r.json()["is_resolved"] is True
    assert client.get("/api/v1/review-items", headers=h).json()["items"] == []

    r = client.post(f"/api/v1/conversations/{cid}/finish", headers=h)
    assert r.status_code == 200
    report = r.json()["report"]
    assert report["total_sentences"] == 1
    assert report["kind_counts"] == {"tense": 1}
    assert "teacher" in report
    assert report["teacher"]["encouragement_zh"]

    # finished conversation cannot send new turns
    r = client.post(
        f"/api/v1/conversations/{cid}/messages",
        headers=h,
        json={"text": "Hello again"},
    )
    assert r.status_code == 409


def test_invalid_teacher_json_falls_back_without_fake_corrections(
    client, h, seed_scenario, monkeypatch
):
    async def fail_chat(**kwargs):
        raise ValueError("bad json")

    monkeypatch.setattr("app.conversation_api.chat_json", fail_chat)

    cid = client.post(
        "/api/v1/conversations", headers=h, json={"scenario_id": seed_scenario}
    ).json()["id"]
    r = client.post(
        f"/api/v1/conversations/{cid}/messages",
        headers=h,
        json={"text": "Hello teacher"},
    )
    assert r.status_code == 200
    turn = r.json()["turn"]
    assert turn["user_message"]["corrections"] == []
    assert turn["assistant_message"]["model_validated"] is False
