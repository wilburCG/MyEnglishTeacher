from app.core.sentence_checker import check_sentence, normalize_tokens

import Levenshtein


def test_exact_and_normalization():
    assert check_sentence("I went home.", "I went home.")["correct"]
    r = check_sentence("  i WENT home  ", "I went home.")
    assert r["correct"]
    assert r["score"] == 100.0
    # 英美拼写、弯引号、缩写
    assert check_sentence("What colour is it?", "What color is it?")["correct"]
    assert check_sentence("i dont like apples", "I don't like apples.")["correct"]
    assert check_sentence("I’m fine.", "I'm fine.")["correct"]


def test_tense_and_form():
    r = check_sentence("I go yesterday.", "I went yesterday.")
    assert not r["correct"]
    assert r["errors"][0]["kind"] == "form"
    assert r["errors"][0]["expected"] == "went"

    r = check_sentence("I like play basketball.", "I like playing basketball.")
    assert any(e["kind"] == "form" for e in r["errors"])


def test_missing_and_extra():
    r = check_sentence("I like basketball.", "I like playing basketball very much.")
    kinds = r["kind_counts"]
    assert kinds.get("missing", 0) >= 2
    assert all(e.get("got") is None for e in r["errors"] if e["kind"] == "missing")

    r = check_sentence("I like it very much today here.", "I like it very much.")
    assert r["kind_counts"].get("extra", 0) >= 2


def test_word_order_reassociation():
    # very 放错位置 + play 形态错：跨块 missing/extra 应被重配
    r = check_sentence(
        "I very like play basketball.",
        "I like playing basketball very much.",
    )
    assert "word_order" in r["kind_counts"]
    assert "form" in r["kind_counts"]


def test_tokens_cover_target():
    r = check_sentence("i go", "I go to school.")
    target_words = [t["target"] for t in r["tokens"] if t["target"]]
    assert target_words == ["i", "go", "to", "school"]


def test_function_words_lower_weight():
    # 错虚词（the 漏了）扣分应轻于错实词
    r_func = check_sentence("I like cat.", "I like the cat.")
    r_content = check_sentence("I like dog.", "I like the cat.")
    assert r_func["score"] > r_content["score"]


def test_garbage_answer_no_far_pairing():
    # 完全不相关的答案：短词不能隔着 2-3 个字符乱配对
    r = check_sentence(
        "I go to school by car yesterday.",
        "How do you get to school? I ride my bike.",
    )
    paired = [e for e in r["errors"] if e["kind"] in ("spelling", "form")]
    assert all(
        abs(len(e["expected"]) - len(e["got"])) <= 1
        and Levenshtein.distance(e["expected"], e["got"])
        <= max(1, len(e["expected"]) // 3)
        for e in paired
    )
    assert r["kind_counts"].get("missing", 0) >= 4


def test_normalize_tokens_contractions():
    assert normalize_tokens("What's I'm don't") == [
        "what", "is", "i", "am", "do", "not"
    ]
