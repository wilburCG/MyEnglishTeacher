import pytest

from app.db import SessionLocal
from app.models import MovieLine, SentencePattern, User


@pytest.fixture(scope="module")
def token(client):
    r = client.post(
        "/api/v1/auth/phone",
        json={"phone": "13511112222", "display_name": "内容同学"},
    )
    assert r.status_code == 200
    return r.json()["token"]


@pytest.fixture(scope="module", autouse=True)
def seed_content(client):
    db = SessionLocal()
    if db.query(SentencePattern).count() == 0:
        db.add(
            SentencePattern(
                level="junior-g7",
                theme="校园生活",
                seq=1,
                template="How much is ...?",
                func_zh="询问价格",
                grammar_point="how much",
                explanation_zh="测试句型",
                examples=[{"en": "How much is it?", "zh": "多少钱？"}],
            )
        )
    if db.query(MovieLine).count() == 0:
        db.add(
            MovieLine(
                show="Friends",
                season=1,
                episode=1,
                character="Monica",
                text_en="I KNOW!",
                text_zh="我知道！",
                level="junior-g7",
                theme="情绪表达",
                seq=1,
            )
        )
    db.commit()
    db.close()
    yield


def test_list_patterns_default_level(client, token):
    r = client.get(
        "/api/v1/patterns",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()["patterns"]
    assert len(data) >= 1
    assert data[0]["template"] == "How much is ...?"
    assert data[0]["favorite"] is False


def test_pattern_favorite_flow(client, token):
    h = {"Authorization": f"Bearer {token}"}
    pid = client.get("/api/v1/patterns", headers=h).json()["patterns"][0]["id"]

    r = client.post(
        "/api/v1/content/favorite",
        headers=h,
        json={"item_type": "pattern", "item_id": pid, "favorite": True},
    )
    assert r.json()["favorite"] is True

    favs = client.get(
        "/api/v1/content/favorites?item_type=pattern", headers=h
    ).json()["patterns"]
    assert any(f["id"] == pid for f in favs)

    # 幂等：重复收藏不报错
    client.post(
        "/api/v1/content/favorite",
        headers=h,
        json={"item_type": "pattern", "item_id": pid, "favorite": True},
    )
    favs2 = client.get(
        "/api/v1/content/favorites?item_type=pattern", headers=h
    ).json()["patterns"]
    assert len(favs2) == len(favs)

    client.post(
        "/api/v1/content/favorite",
        headers=h,
        json={"item_type": "pattern", "item_id": pid, "favorite": False},
    )
    favs3 = client.get(
        "/api/v1/content/favorites?item_type=pattern", headers=h
    ).json()["patterns"]
    assert all(f["id"] != pid for f in favs3)


def test_lines_level_filter_and_search(client, token):
    h = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/v1/lines", headers=h)
    assert r.status_code == 200
    lines = r.json()["lines"]
    assert all(l["level"] == "junior-g7" for l in lines)

    r = client.get("/api/v1/lines?q=KNOW", headers=h)
    assert any("KNOW" in l["text_en"] for l in r.json()["lines"])


def test_admin_required(client, token):
    h = {"Authorization": f"Bearer {token}"}
    r = client.post(
        "/api/v1/admin/patterns",
        headers=h,
        json={
            "level": "junior-g7",
            "theme": "校园生活",
            "template": "test",
            "func_zh": "测试",
        },
    )
    assert r.status_code == 403


def test_admin_crud(client, token):
    db = SessionLocal()
    user = db.query(User).filter(User.phone == "13511112222").first()
    user.role = "admin"
    db.commit()
    db.close()

    h = {"Authorization": f"Bearer {token}"}
    r = client.post(
        "/api/v1/admin/lines",
        headers=h,
        json={
            "show": "Friends",
            "season": 2,
            "episode": 14,
            "character": "Phoebe",
            "text_en": "He's her lobster.",
            "text_zh": "他是她的命中注定。",
            "level": "junior",
            "theme": "家庭与朋友",
            "seq": 99,
        },
    )
    assert r.status_code == 200
    lid = r.json()["id"]

    r = client.patch(
        f"/api/v1/admin/lines/{lid}",
        headers=h,
        json={
            "show": "Friends",
            "character": "Phoebe Buffay",
            "text_en": "He's her lobster.",
            "text_zh": "他是她的命中注定。",
            "level": "junior",
        },
    )
    assert r.status_code == 200
    assert r.json()["character"] == "Phoebe Buffay"

    r = client.delete(f"/api/v1/admin/lines/{lid}", headers=h)
    assert r.status_code == 200
    assert client.get(f"/api/v1/lines/{lid}", headers=h).status_code == 404
