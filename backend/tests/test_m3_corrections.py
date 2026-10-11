import pytest

from app.core.corrections import normalize_teacher_response, summarize_conversation


def test_valid_payload_is_normalized():
    raw = {
        "has_error": True,
        "corrections": [
            {
                "original": "go",
                "corrected": "went",
                "kind": "tense",
                "explanation_zh": "过去时间用过去式",
            }
        ],
        "teacher_reply": "Good! What happened next?",
        "better_version": "I went home.",
        "hint_zh": "",
    }
    out = normalize_teacher_response(raw, "I go home yesterday.")
    assert out["has_error"] is True
    assert out["corrections"][0]["kind"] == "tense"


def test_drops_unlocatable_equal_and_duplicate_corrections():
    raw = {
        "teacher_reply": "Nice.",
        "corrections": [
            {"original": "not-in-sentence", "corrected": "x", "kind": "grammar"},
            {"original": "go", "corrected": "go", "kind": "grammar"},
            {"original": "go", "corrected": "go", "kind": "grammar"},
            {"original": "go", "corrected": "went", "kind": "unknown"},
        ],
    }
    out = normalize_teacher_response(raw, "I go yesterday.")
    assert len(out["corrections"]) == 1
    assert out["corrections"][0]["kind"] == "grammar"
    assert out["has_error"] is True


def test_requires_teacher_reply():
    with pytest.raises(ValueError):
        normalize_teacher_response({"teacher_reply": "  "}, "Hello")


def test_summary_counts():
    messages = [
        {"role": "user", "has_error": True, "corrections": [{"kind": "tense"}, {"kind": "grammar"}]},
        {"role": "user", "has_error": False, "corrections": []},
        {"role": "assistant", "content": "Good"},
    ]
    report = summarize_conversation(
        level="junior-g7",
        scenario_title="Test",
        goal="speak",
        messages=messages,
    )
    assert report["total_sentences"] == 2
    assert report["error_sentences"] == 1
    assert report["accuracy"] == 50.0
    assert report["kind_counts"] == {"tense": 1, "grammar": 1}
