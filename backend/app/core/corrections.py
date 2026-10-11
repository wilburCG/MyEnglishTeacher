"""纠错 JSON 的确定性校验与清洗。

原则：宁漏勿滥。模型返回不合法、original 不在学生原句里、original==corrected、
错误类型不受控时，一律丢弃或降级，避免前端展示误导性批改。
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.core.llm import CORRECTION_KINDS

MAX_CORRECTIONS = 3
MAX_TEXT_LEN = 600


def _clean_text(value: Any, *, fallback: str = "", max_len: int = MAX_TEXT_LEN) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text[:max_len] if len(text) > max_len else text


def normalize_teacher_response(raw: dict[str, Any], user_text: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("teacher response must be a JSON object")

    user_text = _clean_text(user_text)
    teacher_reply = _clean_text(raw.get("teacher_reply"))
    if not teacher_reply:
        raise ValueError("teacher_reply is required")
    if not user_text:
        raise ValueError("user_text is required")

    raw_corrections = raw.get("corrections")
    if raw_corrections is None:
        raw_corrections = []
    if not isinstance(raw_corrections, list):
        raise ValueError("corrections must be a list")

    user_lower = user_text.lower()
    seen: set[tuple[str, str, str]] = set()
    corrections: list[dict[str, str]] = []

    for item in raw_corrections[:10]:
        if not isinstance(item, dict):
            continue
        original = _clean_text(item.get("original"), max_len=200)
        corrected = _clean_text(item.get("corrected"), max_len=200)
        explanation = _clean_text(item.get("explanation_zh"), max_len=220)
        kind = _clean_text(item.get("kind"), max_len=32)

        # 只接受能在学生原句中定位的片段；忽略大小写但保留原始写法展示。
        if not original or not corrected or original.lower() not in user_lower:
            continue
        if original == corrected:
            continue
        if kind not in CORRECTION_KINDS:
            kind = "grammar"
        if not explanation:
            explanation = "注意这个表达，可以按建议修改。"

        key = (original.lower(), corrected.lower(), kind)
        if key in seen:
            continue
        seen.add(key)
        corrections.append(
            {
                "original": original,
                "corrected": corrected,
                "kind": kind,
                "explanation_zh": explanation,
            }
        )
        if len(corrections) >= MAX_CORRECTIONS:
            break

    better_version = _clean_text(raw.get("better_version"))
    if better_version.lower() == user_text.lower():
        better_version = ""

    hint_zh = _clean_text(raw.get("hint_zh"), max_len=220)

    return {
        "has_error": bool(corrections),
        "corrections": corrections,
        "teacher_reply": teacher_reply,
        "better_version": better_version,
        "hint_zh": hint_zh,
        "model_validated": True,
    }


def safe_teacher_fallback(user_text: str) -> dict[str, Any]:
    """LLM/JSON 彻底失败时的最后兜底：不编纠错，只让对话继续。"""
    return {
        "has_error": False,
        "corrections": [],
        "teacher_reply": "That's interesting. Can you tell me more in one more sentence?",
        "better_version": "",
        "hint_zh": "",
        "model_validated": False,
    }


def summarize_conversation(
    *,
    level: str,
    scenario_title: str,
    goal: str,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """确定性对话报告；LLM 总评可在上层额外补充。"""
    user_messages = [m for m in messages if m.get("role") == "user"]
    corrections: list[dict[str, Any]] = []
    kind_counts: dict[str, int] = {}

    for m in user_messages:
        for c in m.get("corrections") or []:
            corrections.append(
                {
                    "original": c.get("original"),
                    "corrected": c.get("corrected"),
                    "kind": c.get("kind"),
                    "explanation_zh": c.get("explanation_zh"),
                }
            )
            kind_counts[c.get("kind", "grammar")] = (
                kind_counts.get(c.get("kind", "grammar"), 0) + 1
            )

    total_sentences = len(user_messages)
    error_sentences = sum(1 for m in user_messages if m.get("has_error"))
    return {
        "level": level,
        "scenario_title": scenario_title,
        "goal": goal,
        "total_sentences": total_sentences,
        "error_sentences": error_sentences,
        "correction_count": len(corrections),
        "kind_counts": kind_counts,
        "corrections": corrections,
        "accuracy": round(
            100.0 * (total_sentences - error_sentences) / total_sentences, 1
        )
        if total_sentences
        else None,
    }
