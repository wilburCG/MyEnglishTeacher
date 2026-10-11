"""M3 真实端到端冒烟：登录 → 场景 → SSE 流式对话 → 纠错 → 复习本 → 报告。"""
import http.client
import json
import random
import sys
import urllib.parse

HOST = "127.0.0.1"
PORT = 3005
PHONE = "136%08d" % random.randint(0, 99999999)


def request(method, path, token=None, body=None, stream=False):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=120)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    conn.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
    resp = conn.getresponse()
    raw = resp.read()
    if resp.status >= 400:
        raise RuntimeError(f"{method} {path} -> {resp.status}: {raw.decode()[:500]}")
    if stream:
        return resp.status, raw.decode()
    return resp.status, json.loads(raw.decode())


def parse_sse(text):
    events = []
    for block in text.split("\n\n"):
        event = "message"
        data = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].strip())
        if data:
            events.append((event, json.loads("".join(data))))
    return events


steps = []


def check(name, ok):
    steps.append((name, bool(ok)))


_, r = request("POST", "/api/v1/auth/phone", body={"phone": PHONE, "display_name": "M3冒烟"})
token = r["token"]

_, r = request("GET", "/api/v1/scenarios", token)
scenarios = r["scenarios"]
check("返回 g7 场景 6 个", len(scenarios) == 6)
scenario = scenarios[0]
check("场景带开场白和推荐词", bool(scenario["opening_line"] and scenario["recommended_words"]))

_, r = request("POST", "/api/v1/conversations", token, {"scenario_id": scenario["id"]})
cid = r["id"]

_, r = request("GET", f"/api/v1/conversations/{cid}", token)
check("开场老师消息已创建", len(r["messages"]) == 1)

_, sse_text = request(
    "POST",
    f"/api/v1/conversations/{cid}/messages/stream",
    token,
    {"text": "I go to school yesterday. I very like play basketball."},
    stream=True,
)
events = parse_sse(sse_text)
deltas = "".join(d["text"] for event, d in events if event == "delta")
finals = [d for event, d in events if event == "final"]
check("SSE 有老师流式增量", len(deltas.strip()) > 10)
check("SSE 有 final 事件", len(finals) == 1)
turn = finals[0]["turn"]
check("用户句子被结构化纠错", len(turn["user_message"]["corrections"]) >= 1)
check("老师回复非空", bool(turn["assistant_message"]["content"].strip()))
check("纠错类型受控", all(c["kind"] in {
    "grammar", "tense", "spelling", "vocabulary", "collocation", "word_order", "pragmatics"
} for c in turn["user_message"]["corrections"]))

_, r = request("GET", f"/api/v1/conversations/{cid}", token)
check("两轮消息均落库", len(r["messages"]) == 3)

_, r = request("POST", f"/api/v1/conversations/{cid}/review-items", token, {"save_all": True})
check("错误可加入复习本", r["count"] >= 1)
_, r2 = request("POST", f"/api/v1/conversations/{cid}/review-items", token, {"save_all": True})
check("复习本保存幂等", r2["count"] == r["count"])

_, r = request("GET", "/api/v1/review-items", token)
check("复习本列表可查", len(r["items"]) >= 1 and r["items"][0]["corrected"])

_, r = request("POST", f"/api/v1/conversations/{cid}/finish", token)
report = r["report"]
check("报告统计句数=1", report["total_sentences"] == 1)
check("报告有错误分布", sum(report["kind_counts"].values()) >= 1)
check("报告有老师中英总评", bool(report["teacher"]["encouragement_zh"] and report["teacher"]["encouragement_en"]))
check("报告有3条建议", len(report["teacher"]["next_tips"]) == 3)

try:
    request("POST", f"/api/v1/conversations/{cid}/messages", token, {"text": "Again"})
    check("结束后禁止再发", False)
except RuntimeError:
    check("结束后禁止再发", True)

ok = all(passed for _, passed in steps)
for name, passed in steps:
    print("PASS" if passed else "FAIL", name)
print("conversation_id=", cid, "phone=", PHONE)
sys.exit(0 if ok else 1)
