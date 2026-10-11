"""听写判题：确定性归一化与词级比对（不调用 LLM）。"""
import re
import unicodedata
from difflib import SequenceMatcher

import Levenshtein

# 常见英美拼写差异：都按正确处理
_UK_TO_US = {
    "colour": "color",
    "colours": "colors",
    "favourite": "favorite",
    "favourites": "favorites",
    "neighbour": "neighbor",
    "neighbours": "neighbors",
    "centre": "center",
    "metre": "meter",
    "litre": "liter",
    "travelling": "traveling",
    "organisation": "organization",
    "realise": "realize",
    "realised": "realized",
    "practise": "practice",
}

_PUNCT_RE = re.compile(r"[^\w\s'-]")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower().strip()
    text = text.replace("’", "'")
    text = _PUNCT_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return " ".join(_UK_TO_US.get(tok, tok) for tok in text.split())


def check_answer(answer: str, target: str) -> dict:
    a = normalize(answer)
    t = normalize(target)
    correct = a == t
    distance = Levenshtein.distance(a, t)
    ratio = SequenceMatcher(None, a, t).ratio()
    return {
        "correct": correct,
        "your_answer": a,
        "target": t,
        "distance": distance,
        "similarity": round(ratio, 3),
    }
