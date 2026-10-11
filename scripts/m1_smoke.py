"""M1 端到端冒烟：注册 -> 队列 -> 卡片复习 -> 听写 -> 发音 -> 统计。"""
import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3005"
PHONE = "136%08d" % __import__("random").randint(0, 99999999)


def call(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
        if r.headers.get("content-type", "").startswith("application/json"):
            body = json.loads(body)
        return r.status, body


steps = []

s, r = call("POST", "/api/v1/auth/phone", body={"phone": PHONE, "display_name": "冒烟同学"})
steps.append(("注册", s == 200))
token = r["token"]
steps.append(("默认级别 junior-g7", r["user"]["level"] == "junior-g7"))

s, r = call("GET", "/api/v1/learn/queue", token)
steps.append(("队列", s == 200 and len(r["new"]) == 10))
w = r["new"][0]
steps.append(("首词有音标", bool(w["phonetic"])))
steps.append(("首词有例句", len(w["examples"]) == 2))

s, r = call("POST", "/api/v1/learn/review", token, {"word_id": w["id"], "grade": 2})
steps.append(("复习 grade=2 次日到期", r["interval_days"] == 1))

s, r = call("POST", "/api/v1/learn/dictation", token, {"word_id": w["id"], "answer": w["headword"].upper() + "!!"})
steps.append(("听写大小写标点归一", r["correct"] is True))

s, r = call("POST", "/api/v1/learn/dictation", token, {"word_id": w["id"], "answer": "zzz_wrong"})
steps.append(("听写错误识别", r["correct"] is False))

s, r = call("POST", "/api/v1/words/%d/favorite" % w["id"], token, {"favorite": True})
steps.append(("收藏", r["favorite"] is True))

s, r = call("GET", "/api/v1/learn/summary", token)
steps.append(("统计已学>=1", r["learned"] >= 1))
steps.append(("streak=1", r["streak_days"] == 1))

# 发音（二进制）
req = urllib.request.Request(BASE + "/api/v1/audio/word/%d" % w["id"])
req.add_header("Authorization", "Bearer " + token)
with urllib.request.urlopen(req, timeout=60) as resp:
    audio = resp.read()
    ctype = resp.headers.get("content-type")
steps.append(("单词发音 mp3", ctype.startswith("audio") and len(audio) > 1000))

# 句子发音
en = w["examples"][0].split("（")[0].split("(")[0].strip()
req = urllib.request.Request(BASE + "/api/v1/audio/sentence?text=" + urllib.parse.quote(en))
req.add_header("Authorization", "Bearer " + token)
with urllib.request.urlopen(req, timeout=60) as resp:
    audio2 = resp.read()
steps.append(("例句发音 mp3", len(audio2) > 1000))

ok = True
for name, passed in steps:
    print(("PASS" if passed else "FAIL"), name)
    ok = ok and passed
print("WORD:", w["headword"], w["phonetic"], "| example:", en)
sys.exit(0 if ok else 1)
