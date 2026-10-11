"""句子听写判题（确定性，不调 LLM）。

词级对齐 + 归一化，把错误分成：
  spelling   拼写错误（词形接近）
  form       时态/形态错误（go/went、play/playing 等）
  missing    漏词
  extra      多写的词
  word_order 词序错误（同一组词位置错位）

大小写、标点、弯引号、缩写(I'm↔I am, don't↔do not)、英美拼写全部归一。
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

import Levenshtein

# 英美拼写统一
_UK_TO_US = {
    "colour": "color", "colours": "colors", "favourite": "favorite",
    "favourites": "favorites", "neighbour": "neighbor",
    "neighbours": "neighbors", "centre": "center", "metre": "meter",
    "litre": "liter", "travelling": "traveling", "organisation": "organization",
    "realise": "realize", "realised": "realized", "practise": "practice",
    "grey": "gray", "honour": "honor", "labour": "labor",
    "behaviour": "behavior", "analyse": "analyze",
}

# 缩写展开（含漏写撇号的高频学生写法；不收录本身是实词的 lets/its/ill）
_CONTRACTIONS = {
    "i'm": "i am", "you're": "you are", "we're": "we are",
    "they're": "they are", "he's": "he is", "she's": "she is",
    "it's": "it is", "that's": "that is", "there's": "there is",
    "here's": "here is", "what's": "what is", "who's": "who is",
    "how's": "how is", "where's": "where is",
    "don't": "do not", "doesn't": "does not", "didn't": "did not",
    "isn't": "is not", "aren't": "are not", "wasn't": "was not",
    "weren't": "were not", "can't": "can not", "couldn't": "could not",
    "won't": "will not", "wouldn't": "would not", "shouldn't": "should not",
    "hasn't": "has not", "haven't": "have not", "hadn't": "had not",
    "mustn't": "must not", "needn't": "need not",
    "i'll": "i will", "you'll": "you will", "we'll": "we will",
    "they'll": "they will", "he'll": "he will", "she'll": "she will",
    "it'll": "it will", "that'll": "that will",
    "i've": "i have", "you've": "you have", "we've": "we have",
    "they've": "they have", "could've": "could have", "would've": "would have",
    "i'd": "i would", "you'd": "you would", "he'd": "he would",
    "she'd": "she would", "they'd": "they would", "we'd": "we would",
    "let's": "let us", "gonna": "going to", "wanna": "want to",
    "gimme": "give me", "gotta": "got to", "kinda": "kind of",
    "cause": "because",
    # 漏写撇号
    "im": "i am", "youre": "you are", "theyre": "they are", "thats": "that is",
    "whats": "what is", "dont": "do not", "doesnt": "does not",
    "didnt": "did not", "isnt": "is not", "arent": "are not",
    "wasnt": "was not", "werent": "were not", "cant": "can not",
    "couldnt": "could not", "wont": "will not", "wouldnt": "would not",
    "shouldnt": "should not", "hasnt": "has not", "havent": "have not",
    "hadnt": "had not",
}

# 虚词权重低，实词权重高
_FUNCTION_WORDS = {
    "a", "an", "the", "is", "am", "are", "was", "were", "be", "been",
    "being", "do", "does", "did", "have", "has", "had", "will", "would",
    "can", "could", "should", "shall", "may", "might", "must", "i",
    "you", "he", "she", "it", "we", "they", "me", "him", "her", "us",
    "them", "my", "your", "his", "its", "our", "their", "this", "that",
    "these", "those", "in", "on", "at", "to", "for", "of", "with",
    "from", "by", "about", "as", "into", "onto", "up", "down", "out",
    "off", "over", "under", "and", "or", "but", "so", "if", "then",
    "than", "too", "very", "not", "no", "yes", "there", "here",
}

_PUNCT_RE = re.compile(r"[^\w\s'-]")


def normalize_tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text).lower().strip()
    text = text.replace("’", "'").replace("‘", "'")
    text = _PUNCT_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    out: list[str] = []
    for tok in (t for t in text.split(" ") if t):
        tok = _UK_TO_US.get(tok, tok)
        expanded = _CONTRACTIONS.get(tok)
        if expanded:
            out.extend(expanded.split(" "))
        else:
            out.append(tok)
    return out


def _word_weight(tok: str) -> float:
    return 0.5 if tok in _FUNCTION_WORDS else 1.0


_IRREGULAR_FORMS = {
    ("go", "went"), ("go", "gone"), ("goes", "went"), ("goes", "gone"),
    ("is", "was"), ("am", "was"), ("are", "were"),
    ("have", "has"), ("have", "had"), ("has", "had"),
    ("do", "does"), ("do", "did"), ("does", "did"),
    ("eat", "ate"), ("see", "saw"), ("get", "got"), ("give", "gave"),
    ("take", "took"), ("come", "came"), ("make", "made"), ("run", "ran"),
    ("say", "said"), ("tell", "told"), ("buy", "bought"),
    ("think", "thought"), ("bring", "brought"), ("teach", "taught"),
    ("catch", "caught"), ("good", "better"), ("good", "best"),
    ("bad", "worse"),
}


def _stem(w: str) -> str:
    """保守还原常见屈折后缀。"""
    for suf in ("ing", "ied", "ies", "ed", "es", "s", "er", "est"):
        if len(w) > len(suf) + 1 and w.endswith(suf):
            base = w[: -len(suf)]
            if suf == "ing":
                # running→run（去重复辅音）；making→make；going→go
                if len(base) > 2 and base[-1] == base[-2]:
                    return base[:-1]
                return base + "e" if base.endswith(("k", "m", "n", "v", "g")) and len(base) <= 3 else base
            if suf in ("ied", "ies"):
                return base + "y"
            if suf == "ed":
                if base.endswith("i"):
                    return base[:-1] + "y"
                return base
            if suf in ("er", "est") and len(base) > 2 and base[-1] == base[-2]:
                return base[:-1]
            if suf in ("es", "s", "er", "est"):
                return base
    return w


def _same_stem(a: str, b: str) -> bool:
    if a == b:
        return False
    if (a, b) in _IRREGULAR_FORMS or (b, a) in _IRREGULAR_FORMS:
        return True
    return _stem(a) == _stem(b)


def _classify_pair(expected: str, got: str) -> str:
    """replace 配对的两个词：形态错误优先，其次拼写。"""
    if _same_stem(expected, got):
        return "form"
    dist = Levenshtein.distance(expected, got)
    if dist <= max(1, round(len(expected) * 0.35)):
        return "spelling"
    if expected.startswith(got) or got.startswith(expected):
        return "form"
    if dist <= 2:
        return "spelling"
    return "form"


def _pair_close(e: str, g: str) -> bool:
    """长度不等的 replace 块里，两个词是否值得配对。"""
    d = Levenshtein.distance(e, g)
    if _same_stem(e, g):
        return True
    # 短词必须几乎一致（3-4 字母词距离 1），长词允许 1/3 误差
    return d <= max(1, len(e) // 3)


def _merged_blocks(answer: list[str], expected: list[str]) -> list[tuple]:
    """把相邻 delete/insert 合成 replace 块，便于交叉近形配对。"""
    raw = SequenceMatcher(a=answer, b=expected, autojunk=False).get_opcodes()
    blocks: list[tuple] = []
    for op in raw:
        if blocks:
            prev = blocks[-1]
            ptag, pi1, pi2, pj1, pj2 = prev
            # delete 后紧跟 insert，或反过来 → 合并成 replace
            if (ptag, op[0]) in (("delete", "insert"), ("insert", "delete")):
                blocks[-1] = (
                    "replace",
                    min(pi1, op[1]),
                    max(pi2, op[2]),
                    min(pj1, op[3]),
                    max(pj2, op[4]),
                )
                continue
        blocks.append(op)
    return blocks


def _emit_pair(e: str, g: str, result_tokens: list, errors: list,
               used_pairs: list) -> None:
    kind = _classify_pair(e, g)
    result_tokens.append(
        {"target": e, "answer": g, "status": "wrong", "kind": kind}
    )
    errors.append({"kind": kind, "expected": e, "got": g})
    used_pairs.append((g, e))


def _render(expected: list[str], answer: list[str]) -> tuple[list[dict], list[dict]]:
    result_tokens: list[dict] = []
    errors: list[dict] = []
    used_pairs: list[tuple[str, str]] = []

    for tag, i1, i2, j1, j2 in _merged_blocks(answer, expected):
        got_words = answer[i1:i2]
        exp_words = expected[j1:j2]

        if tag == "equal":
            for w in exp_words:
                result_tokens.append({"target": w, "answer": w, "status": "ok"})

        elif tag == "replace":
            if len(got_words) == len(exp_words):
                for g, e in zip(got_words, exp_words):
                    if g == e:
                        result_tokens.append(
                            {"target": e, "answer": g, "status": "ok"}
                        )
                    elif _pair_close(e, g):
                        _emit_pair(e, g, result_tokens, errors, used_pairs)
                    else:
                        # 词形不沾边：按“多词 + 漏词”处理，避免乱配对误导
                        result_tokens.append(
                            {"target": None, "answer": g, "status": "extra", "kind": "extra"}
                        )
                        errors.append({"kind": "extra", "expected": None, "got": g})
                        result_tokens.append(
                            {"target": e, "answer": None, "status": "missing", "kind": "missing"}
                        )
                        errors.append({"kind": "missing", "expected": e, "got": None})
                continue

            # 贪心近形配对（每词只用一次）
            candidates = []
            for gi, g in enumerate(got_words):
                for ei, e in enumerate(exp_words):
                    if _pair_close(e, g):
                        d = Levenshtein.distance(e, g)
                        candidates.append((d, gi, ei))
            candidates.sort()
            g_paired: dict[int, int] = {}
            e_used: set[int] = set()
            for _, gi, ei in candidates:
                if gi in g_paired or ei in e_used:
                    continue
                g_paired[gi] = ei
                e_used.add(ei)

            gi = ei = 0
            while gi < len(got_words) or ei < len(exp_words):
                g = got_words[gi] if gi < len(got_words) else None
                e = exp_words[ei] if ei < len(exp_words) else None
                if g is not None and g_paired.get(gi) == ei:
                    _emit_pair(e, g, result_tokens, errors, used_pairs)
                    gi += 1
                    ei += 1
                elif g is not None and gi not in g_paired:
                    result_tokens.append(
                        {"target": None, "answer": g, "status": "extra", "kind": "extra"}
                    )
                    errors.append({"kind": "extra", "expected": None, "got": g})
                    gi += 1
                elif e is not None:
                    result_tokens.append(
                        {"target": e, "answer": None, "status": "missing", "kind": "missing"}
                    )
                    errors.append({"kind": "missing", "expected": e, "got": None})
                    ei += 1
                else:
                    gi += 1
                    ei += 1

        elif tag == "delete":  # 学生写了、目标没有 → 多词
            for g in got_words:
                result_tokens.append(
                    {"target": None, "answer": g, "status": "extra", "kind": "extra"}
                )
                errors.append({"kind": "extra", "expected": None, "got": g})

        elif tag == "insert":  # 目标有、学生没写 → 漏词
            for e in exp_words:
                result_tokens.append(
                    {"target": e, "answer": None, "status": "missing", "kind": "missing"}
                )
                errors.append({"kind": "missing", "expected": e, "got": None})

    # 词序检测：配对里出现互换（A→B、B→A）升级为 word_order
    swapped: set[tuple[str, str]] = set()
    for i, (g1, e1) in enumerate(used_pairs):
        for g2, e2 in used_pairs[i + 1:]:
            if g1 == e2 and g2 == e1 and g1 != g2:
                swapped.add(tuple(sorted((g1, e1))))
    if swapped:
        for tok in result_tokens:
            if tok["status"] != "wrong":
                continue
            key = tuple(sorted((str(tok["answer"]), str(tok["target"]))))
            if key in swapped:
                tok["kind"] = "word_order"
        for err in errors:
            if err["kind"] in ("spelling", "form") and err["got"] and err["expected"]:
                key = tuple(sorted((err["got"], err["expected"])))
                if key in swapped:
                    err["kind"] = "word_order"

    # 跨块重配：SequenceMatcher 的锚点可能把本该配对的词拆成 missing+extra，
    # 这里在 missing/extra 之间做一次贪心近形/同词配对。
    result_tokens, errors = _reassociate(result_tokens, errors)

    return result_tokens, errors


def _reassociate(tokens, errors):
    """跨块重配 missing/extra：同词错位 word_order，同根 form，近形 spelling。"""
    missing_idx = [i for i, t in enumerate(tokens) if t["status"] == "missing"]
    extra_idx = [i for i, t in enumerate(tokens) if t["status"] == "extra"]
    if not missing_idx or not extra_idx:
        return tokens, errors

    candidates = []
    for mi in missing_idx:
        e = str(tokens[mi]["target"])
        for xi in extra_idx:
            g = str(tokens[xi]["answer"])
            if e == g:
                rank, kind = 0, "word_order"
            elif _same_stem(e, g):
                rank, kind = 1, "form"
            elif _pair_close(e, g):
                rank, kind = 2, _classify_pair(e, g)
            else:
                continue
            candidates.append((rank, Levenshtein.distance(e, g), mi, xi, kind))
    candidates.sort()

    matched_m = {}
    matched_x = set()
    for _rank, _dist, mi, xi, kind in candidates:
        if mi in matched_m or xi in matched_x:
            continue
        matched_m[mi] = (xi, kind)
        matched_x.add(xi)

    if not matched_m:
        return tokens, errors

    pairs = []
    for mi, (xi, kind) in matched_m.items():
        pairs.append((str(tokens[mi]["target"]), str(tokens[xi]["answer"]), kind))

    # errors 中对应的 missing/extra 条目按配对数剔除（兼容重复词）
    m_left = {}
    x_left = {}
    for e_word, g_word, _kind in pairs:
        m_left[e_word] = m_left.get(e_word, 0) + 1
        x_left[g_word] = x_left.get(g_word, 0) + 1

    new_errors = []
    for err in errors:
        if err.get("kind") == "missing" and m_left.get(err.get("expected"), 0) > 0:
            m_left[err["expected"]] -= 1
            continue
        if err.get("kind") == "extra" and x_left.get(err.get("got"), 0) > 0:
            x_left[err["got"]] -= 1
            continue
        new_errors.append(err)

    new_tokens = []
    for i, tok in enumerate(tokens):
        if tok["status"] == "missing" and i in matched_m:
            xi, kind = matched_m[i]
            e_word = str(tok["target"])
            g_word = str(tokens[xi]["answer"])
            new_tokens.append(
                {"target": e_word, "answer": g_word, "status": "wrong", "kind": kind}
            )
            new_errors.append({"kind": kind, "expected": e_word, "got": g_word})
        elif tok["status"] == "extra" and i in matched_x:
            continue
        else:
            new_tokens.append(tok)
    return new_tokens, new_errors


def check_sentence(answer: str, target: str) -> dict:
    expected = normalize_tokens(target)
    got = normalize_tokens(answer)
    correct = expected == got
    tokens, errors = _render(expected, got)

    total_w = sum(_word_weight(w) for w in expected)
    got_w = sum(
        _word_weight(str(t["target"]))
        for t in tokens
        if t["status"] == "ok" and t["target"]
    )
    # 词序错位：词写对了但位置错，给一半分
    got_w += 0.5 * sum(
        _word_weight(str(t["target"]))
        for t in tokens
        if t["status"] == "wrong" and t.get("kind") == "word_order"
    )
    # extra 词轻微扣分，避免多写一堆无关词也拿高分
    extra_count = sum(1 for t in tokens if t["status"] == "extra")
    score = max(0.0, round(100.0 * got_w / max(total_w, 1) - extra_count * 2.5, 1))
    if correct:
        score = 100.0

    kind_counts: dict[str, int] = {}
    for e in errors:
        kind_counts[e["kind"]] = kind_counts.get(e["kind"], 0) + 1

    return {
        "correct": correct,
        "score": score,
        "your_answer": " ".join(got),
        "target": " ".join(expected),
        "tokens": tokens,
        "errors": errors,
        "kind_counts": kind_counts,
    }
