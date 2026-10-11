"""M2 端到端冒烟：句型/台词列表、级别过滤、搜索、收藏、台词发音。"""
import json
import random
import sys
import urllib.parse
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3005"
PHONE = "135%08d" % random.randint(0, 99999999)


def call(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read())


steps = []
_, r = call("POST", "/api/v1/auth/phone",
            body={"phone": PHONE, "display_name": "M2冒烟"})
token = r["token"]

_, r = call("GET", "/api/v1/patterns", token)
steps.append(("初一句型 24 条", len(r["patterns"]) == 24))
p = r["patterns"][0]
steps.append(("句型带例句和讲解", bool(p["examples"]) and bool(p["func_zh"])))

_, r = call(
    "POST",
    "/api/v1/content/favorite",
    token,
    {"item_type": "pattern", "item_id": p["id"], "favorite": True},
)
steps.append(("收藏句型", r["favorite"] is True))

_, r = call("GET", "/api/v1/lines", token)
steps.append(("台词默认只看本级(g7=5)", len(r["lines"]) == 5))

_, r = call("GET", "/api/v1/lines?include_all_levels=true", token)
all_lines = r["lines"]
steps.append(("全部级别台词 20 条", len(all_lines) == 20))

_, r = call("GET", "/api/v1/lines?q=" + urllib.parse.quote("KNOW"), token)
steps.append(("搜索 I KNOW", any("KNOW" in x["text_en"] for x in r["lines"])))

line = next(x for x in all_lines if x["text_en"] == "I got off the plane.")
_, r = call(
    "POST",
    "/api/v1/content/favorite",
    token,
    {"item_type": "line", "item_id": line["id"], "favorite": True},
)
steps.append(("收藏台词", r["favorite"] is True))

_, r = call("GET", "/api/v1/content/favorites?item_type=line", token)
steps.append(("收藏夹含台词", len(r["lines"]) == 1))

_, r = call("GET", "/api/v1/learn/summary", token)
steps.append(("summary 含内容收藏数", r["content_favorites"] == 2))

req = urllib.request.Request(
    BASE
    + "/api/v1/audio/sentence?text="
    + urllib.parse.quote("I got off the plane.")
)
req.add_header("Authorization", "Bearer " + token)
with urllib.request.urlopen(req, timeout=60) as resp:
    audio = resp.read()
steps.append(("台词发音 mp3", len(audio) > 1000))

ok = all(passed for _, passed in steps)
for name, passed in steps:
    print("PASS" if passed else "FAIL", name)
sys.exit(0 if ok else 1)
