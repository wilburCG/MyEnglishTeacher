"""M4 句子听写实烟：队列/常慢速音频/判题/错句入复习本/连续两次掌握/多材料源。"""
import http.client
import json
import random
import sys

HOST, PORT = "127.0.0.1", 3005
PHONE = "137%08d" % random.randint(0, 99999999)


def call(method, path, token="", body=None, raw=False):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=120)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    conn.request(
        method, path,
        body=json.dumps(body) if body is not None else None,
        headers=headers,
    )
    resp = conn.getresponse()
    data = resp.read()
    if resp.status >= 400:
        raise RuntimeError("%s %s -> %s: %s" % (method, path, resp.status, data[:300]))
    if raw:
        return resp.status, resp.headers.get("Content-Type", ""), data
    return resp.status, json.loads(data.decode())


steps = []


def check(name, ok):
    steps.append((name, bool(ok)))


_, r = call("POST", "/api/v1/auth/phone", body={"phone": PHONE, "display_name": "M4冒烟"})
token = r["token"]

# 1) 句型队列不回传原文
_, r = call("GET", "/api/v1/dictation/sentence-queue?source=patterns&limit=10", token)
items = r["items"]
check("句型队列非空", len(items) >= 1)
check("队列隐藏原文", all("target" not in x for x in items))
item = items[0]

# 2) 常速 + 慢速音频
_, ctype, audio1 = call(
    "GET",
    "/api/v1/dictation/audio?source_type=%s&source_id=%s&sentence_index=%s&speed=normal"
    % (item["source_type"], item["source_id"], item["sentence_index"]),
    token,
    raw=True,
)
_, _, audio2 = call(
    "GET",
    "/api/v1/dictation/audio?source_type=%s&source_id=%s&sentence_index=%s&speed=slow"
    % (item["source_type"], item["source_id"], item["sentence_index"]),
    token,
    raw=True,
)
check("常速音频 mp3", ctype.startswith("audio/") and len(audio1) > 1000)
check("慢速音频 mp3", len(audio2) > 1000)

# 3) 故意答错 → 进复习本
_, r = call("POST", "/api/v1/dictation/sentence-check", token, {
    "source_type": item["source_type"],
    "source_id": item["source_id"],
    "sentence_index": item["sentence_index"],
    "answer": "totally wrong answer here",
    "hint_count": 2,
})
target = r["target"]
check("答错判定", r["correct"] is False)
check("错误入库并加入复习本", r["review_action"] == "added")
check("返回逐词结果", len(r["tokens"]) > 0 and sum(r["kind_counts"].values()) > 0)

# 4) 复习队列能取到
_, r = call("GET", "/api/v1/dictation/sentence-queue?source=review", token)
review = r["items"]
check("错句进复习队列", any(x["source_type"] == "review" for x in review))
ritem = next(x for x in review if x["source_type"] == "review")
review_id = ritem["source_id"]

# 5) 第一次对：streak=1
_, r = call("POST", "/api/v1/dictation/sentence-check", token, {
    "source_type": item["source_type"],
    "source_id": item["source_id"],
    "sentence_index": item["sentence_index"],
    "answer": target,
    "hint_count": 0,
})
check("第一次正确 streak=1", r["review_action"] == "streak" and r["review_streak"] == 1)

# 6) 通过复习入口第二次对：掌握
_, r = call("POST", "/api/v1/dictation/sentence-check", token, {
    "source_type": "review",
    "source_id": review_id,
    "sentence_index": 0,
    "answer": target,
    "hint_count": 0,
})
check("第二次正确掌握", r["review_action"] == "mastered" and r["review_streak"] == 2)

_, r = call("GET", "/api/v1/dictation/sentence-queue?source=review", token)
check("掌握后退出复习队列", all(x["source_id"] != review_id for x in r["items"]))

# 7) 大小写/标点/缩写归一判对（取一条台词）
_, r = call("GET", "/api/v1/dictation/sentence-queue?source=lines&limit=3", token)
lines = r["items"]
check("台词队列非空", len(lines) >= 1)
line_item = lines[0]
# 用先错后从结果拿 target 再原样提交的方式验证完全正确路径
_, r = call("POST", "/api/v1/dictation/sentence-check", token, {
    "source_type": line_item["source_type"],
    "source_id": line_item["source_id"],
    "sentence_index": 0,
    "answer": "xyz",
})
target_line = r["target"]
_, r = call("POST", "/api/v1/dictation/sentence-check", token, {
    "source_type": line_item["source_type"],
    "source_id": line_item["source_id"],
    "sentence_index": 0,
    "answer": target_line.upper() + " ???",
})
check("大小写标点归一判对", r["correct"] is True and r["score"] == 100.0)

# 8) auto 队列可用
_, r = call("GET", "/api/v1/dictation/sentence-queue?source=auto&limit=5", token)
check("智能复习队列", len(r["items"]) >= 1)

# 9) 未登录 401
conn = http.client.HTTPConnection(HOST, PORT)
conn.request("GET", "/api/v1/dictation/sentence-queue")
check("未登录 401", conn.getresponse().status == 401)

ok = all(p for _, p in steps)
for name, passed in steps:
    print("PASS" if passed else "FAIL", name)
sys.exit(0 if ok else 1)
