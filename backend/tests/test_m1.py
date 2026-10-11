# 测试环境由 conftest.py 统一配置（sqlite + 临时库 + client fixture）


def _token(client, phone="13800138000", name="测试同学"):
    r = client.post(
        "/api/v1/auth/phone",
        json={"phone": phone, "display_name": name},
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_phone_register_and_login(client):
    r = client.post("/api/v1/auth/phone", json={"phone": "13900139000"})
    assert r.status_code == 400
    token = _token(client, phone="13900139000")
    r = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    assert r.json()["level"] == "junior-g7"
    # 老用户二次登录不需要昵称
    r2 = client.post("/api/v1/auth/phone", json={"phone": "13900139000"})
    assert r2.status_code == 200


def test_queue_review_dictation_flow(client):
    token = _token(client, phone="13700137000")
    h = {"Authorization": f"Bearer {token}"}

    q = client.get("/api/v1/learn/queue", headers=h).json()
    assert q["counts"]["new"] >= 2
    word_id = q["new"][0]["id"]

    r = client.post(
        "/api/v1/learn/review",
        headers=h,
        json={"word_id": word_id, "grade": 2},
    )
    assert r.status_code == 200
    assert r.json()["interval_days"] == 1

    # 听写：错误拼写 -> False；正确拼写（大小写/标点/空格归一）-> True
    r = client.post(
        "/api/v1/learn/dictation",
        headers=h,
        json={"word_id": word_id, "answer": "abando"},
    )
    assert r.json()["correct"] is False

    r = client.post(
        "/api/v1/learn/dictation",
        headers=h,
        json={"word_id": word_id, "answer": " Abandon! "},
    )
    assert r.json()["correct"] is True

    s = client.get("/api/v1/learn/summary", headers=h).json()
    assert s["learned"] >= 1
    assert s["today_reviews"] >= 3


def test_dictation_normalization():
    from app.core.checker import check_answer

    assert check_answer("favourite", "favorite")["correct"] is True
    assert check_answer("don’t", "Don't")["correct"] is True
    assert check_answer("Don't!", "don't")["correct"] is True
    assert check_answer("abandons", "abandon")["correct"] is False


def test_srs_ladder():
    from app.core.srs import SrsState, schedule

    s = SrsState()
    s = schedule(s, 2)
    assert s.interval_days == 1 and s.reps == 1
    s = schedule(s, 2)
    assert s.interval_days == 3 and s.reps == 2
    s = schedule(s, 3)
    assert s.reps == 3 and s.interval_days >= 7
    # again 重置
    s = schedule(s, 0)
    assert s.reps == 0 and s.interval_days == 0 and s.lapses == 1
    # ease 有下限
    for _ in range(10):
        s = schedule(s, 0)
    assert s.ease_factor >= 1.3
