"""ECDICT + 七年级教材词表导入（幂等）。

用法（容器内）：
  python -m scripts.import_ecdict --csv /seed/ecdict.csv --g7 /seed/g7
"""
import argparse
import csv
import glob
import json
import os

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Word

LEVEL_TAGS = [
    ("junior", {"zk"}),
    ("senior", {"gk"}),
    ("cet4", {"cet4"}),
    ("cet6", {"cet6", "ky"}),
    ("ielts", {"ielts"}),
]

G7_ORDER = [
    "starter_unit_1.json",
    "starter_unit_2.json",
    "starter_unit_3.json",
    "unit_1.json",
    "unit_2.json",
    "unit_3.json",
    "unit_4.json",
    "unit_5.json",
    "unit_6.json",
    "unit_7.json",
]


def load_g7(g7_dir: str) -> dict:
    result = {}
    seq = 0
    for fname in G7_ORDER:
        path = os.path.join(g7_dir, fname)
        if not os.path.exists(path):
            continue
        for item in json.load(open(path, encoding="utf-8")):
            word = item["word"].strip().lower()
            if not word or word in result:
                continue
            seq += 1
            result[word] = {
                "phonetic": item.get("phonetic") or None,
                "pos": item.get("partOfSpeech") or None,
                "translation": item.get("meaning") or None,
                "examples": item.get("exampleSentences") or [],
                "unit": item.get("unit") or fname.replace(".json", ""),
                "seq": seq,
            }
    return result


def level_for(tags: set[str]) -> str | None:
    for level, wanted in LEVEL_TAGS:
        if tags & wanted:
            return level
    return None


def to_int(value: str) -> int | None:
    try:
        return int(value) if value else None
    except ValueError:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="/seed/ecdict.csv")
    parser.add_argument("--g7", default="/seed/g7")
    args = parser.parse_args()

    g7 = load_g7(args.g7)
    print(f"g7 words: {len(g7)}")

    db = SessionLocal()
    existing = {
        w.headword: w for w in db.scalars(select(Word)).all()
    }
    print(f"existing words: {len(existing)}")

    # 先收集各考纲级别的行，按词频排名赋 seq
    collected = {"junior": [], "senior": [], "cet4": [], "cet6": [], "ielts": []}
    g7_ecdict = {}
    rows = csv.DictReader(open(args.csv, encoding="utf-8"))
    for row in rows:
        head = row["word"].strip().lower()
        if not head or " " in head:
            continue
        tags = set((row.get("tag") or "").split())
        if head in g7:
            g7_ecdict[head] = row
            continue
        level = level_for(tags)
        if level is None:
            continue
        collected[level].append((head, row, to_int(row.get("frq") or "")))

    created = 0
    updated = 0

    def upsert(head: str, level: str, seq: int, data: dict):
        nonlocal created, updated
        obj = existing.get(head)
        if obj is None:
            obj = Word(headword=head)
            db.add(obj)
            created += 1
        else:
            updated += 1
        obj.level = level
        obj.seq = seq
        for key, value in data.items():
            setattr(obj, key, value)

    # g7（教材元数据为主，合并 ECDICT 音标/释义）
    for head, meta in g7.items():
        ec = g7_ecdict.get(head)
        upsert(
            head,
            "junior-g7",
            meta["seq"],
            {
                "phonetic": meta["phonetic"] or (ec or {}).get("phonetic"),
                "pos": meta["pos"],
                "translation": meta["translation"] or (ec or {}).get("translation"),
                "definition_en": (ec or {}).get("definition") or None,
                "examples": meta["examples"],
                "unit": meta["unit"],
                "tag": "g7",
                "frq": to_int((ec or {}).get("frq") or ""),
                "bnc": to_int((ec or {}).get("bnc") or ""),
                "collins": to_int((ec or {}).get("collins") or ""),
                "oxford": to_int((ec or {}).get("oxford") or ""),
            },
        )

    # 其他级别：词频排名升序（越常见越先学）
    for level, items in collected.items():
        items.sort(
            key=lambda x: (
                x[2] is None or x[2] == 0,
                x[2] if x[2] else 0,
            )
        )
        for seq, (head, row, frq) in enumerate(items, start=1):
            upsert(
                head,
                level,
                seq,
                {
                    "phonetic": row.get("phonetic") or None,
                    "pos": row.get("pos") or None,
                    "definition_en": row.get("definition") or None,
                    "translation": row.get("translation") or None,
                    "tag": row.get("tag") or None,
                    "frq": frq,
                    "bnc": to_int(row.get("bnc") or ""),
                    "collins": to_int(row.get("collins") or ""),
                    "oxford": to_int(row.get("oxford") or ""),
                    "examples": None,
                    "unit": None,
                },
            )

    db.commit()
    count = db.query(Word).count()
    print(f"done. created={created} updated={updated} total={count}")
    from collections import Counter

    dist = Counter(w.level for w in db.scalars(select(Word)).all())
    print(dict(dist))


if __name__ == "__main__":
    main()
