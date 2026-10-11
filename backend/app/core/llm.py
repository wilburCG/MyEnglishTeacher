"""火山方舟 ARK 客户端：英文对话老师 + 结构化纠错。"""
from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import get_settings

LEVEL_GUIDANCE = {
    "junior-g7": "CEFR A1，初一水平。只用最基础词汇和短句，避免复杂从句。",
    "junior": "CEFR A1-A2，初中/中考水平。句子简短清楚。",
    "senior": "CEFR A2-B1，高中/高考水平。可使用常见从句和时态。",
    "cet4": "CEFR B1，大学四级水平。",
    "cet6": "CEFR B2，六级/考研水平。",
    "ielts": "CEFR B2+，雅思/托福水平，可使用更丰富、地道的表达。",
}

CORRECTION_KINDS = {
    "grammar",
    "tense",
    "spelling",
    "vocabulary",
    "collocation",
    "word_order",
    "pragmatics",
}


def _strip_json_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def build_teacher_system_prompt(
    *,
    level: str,
    scenario_title: str,
    teacher_persona: str,
    goal: str,
    recommended_words: list[str] | None = None,
    history: list[dict[str, str]] | None = None,
    turn_index: int = 0,
) -> str:
    """严格 JSON 输出提示。模型只返回 JSON，前端自行流式/卡片渲染。"""
    level_guide = LEVEL_GUIDANCE.get(level, LEVEL_GUIDANCE["junior-g7"])
    words = ", ".join(recommended_words or []) or "无"
    history_text = "\n".join(
        f"{('Student' if m['role'] == 'user' else 'Teacher')}: {m['content']}"
        for m in (history or [])[-12:]
    ) or "无"

    return f"""You are a warm, encouraging English teacher in a role-play scenario.

Student level: {level} — {level_guide}
Scenario: {scenario_title}
Teacher persona: {teacher_persona}
Task goal: {goal}
Recommended words to naturally encourage (do not force): {words}
Current turn: {turn_index}

Rules:
1. Teach English only. If the student asks about unrelated or unsafe topics, politely bring them back to the English role-play.
2. Keep the teacher reply appropriate for the student's level. Normally 1-2 short sentences for junior-g7.
3. React naturally, advance the scenario, and end with one clear follow-up question.
4. Correct real errors only. Precision over recall. Do not invent errors and do not over-correct acceptable informal English.
5. If the sentence is understandable and correct, return an empty corrections array.
6. Each correction must quote an exact substring from the student sentence. The corrected text must be different from the original.
7. Use only these kinds: grammar (verb forms, articles, plural, auxiliary verbs, clause structure), tense (time-related tense choice), spelling, vocabulary, collocation (prepositions, adverb+verb, fixed word partners), word_order, pragmatics.
8. Explain in simple Chinese. Keep explanations short and kind.
9. "better_version" is optional. Use it only when the sentence is understandable but can sound more natural. It must not duplicate a correction-only response.
10. If the student seems stuck, you may give one small hint in teacher_reply, but still ask a simple question.

Recent conversation:
{history_text}

Return ONLY one minified JSON object, no Markdown, with this exact schema:
{{
  "has_error": true/false,
  "corrections": [
    {{
      "original": "exact student substring",
      "corrected": "corrected substring",
      "kind": "grammar|tense|spelling|vocabulary|collocation|word_order|pragmatics",
      "explanation_zh": "简短中文讲解"
    }}
  ],
  "teacher_reply": "English reply and one follow-up question",
  "better_version": "optional more natural full sentence, or empty string",
  "hint_zh": "optional short Chinese hint, or empty string"
}}"""


def build_user_prompt(scenario_title: str, user_text: str) -> str:
    return f"Scenario: {scenario_title}\nStudent says: {user_text}\n\nReturn the JSON object now."


def normalize_teacher_payload(raw: dict[str, Any], user_text: str) -> dict[str, Any]:
    """后端二次校验，防止模型误人子弟；由 core/corrections.py 实现。"""
    from app.core.corrections import normalize_teacher_response

    return normalize_teacher_response(raw, user_text)


class _JsonStringStreamParser:
    """从流式 JSON 中提前抽出 teacher_reply 字符串，实现用户可见的逐词输出。

    模型仍在最后生成完整 JSON；这里只把固定字段的字符串增量解码出来。
    """

    def __init__(self, key: str = "teacher_reply"):
        self.key = key
        self.buf = ""
        self.located = False
        self.str_start = -1
        self.decoded = ""
        self.closed = False

    def feed(self, chunk: str) -> str:
        self.buf += chunk
        if not self.located:
            marker = '"' + self.key + '"'
            pos = self.buf.find(marker)
            if pos < 0:
                return ""
            rest = self.buf[pos + len(marker):]
            colon = rest.find(":")
            if colon < 0:
                return ""
            quote = rest.find('"', colon + 1)
            if quote < 0:
                return ""
            self.str_start = pos + len(marker) + colon + 1 + quote
            self.located = True

        raw = self.buf[self.str_start + 1:]
        decoded, closed = _scan_json_string(raw)
        if closed:
            self.closed = True
        delta = decoded[len(self.decoded):]
        self.decoded = decoded
        return delta


def _scan_json_string(raw: str) -> tuple[str, bool]:
    out: list[str] = []
    escaped = False
    i = 0
    escapes = {
        '"': '"',
        "\\": "\\",
        "/": "/",
        "b": "\b",
        "f": "\f",
        "n": "\n",
        "r": "\r",
        "t": "\t",
    }
    while i < len(raw):
        ch = raw[i]
        if escaped:
            if ch == "u":
                if i + 4 >= len(raw):
                    return "".join(out), False
                hex_part = raw[i + 1:i + 5]
                if len(hex_part) != 4:
                    return "".join(out), False
                try:
                    out.append(chr(int(hex_part, 16)))
                except ValueError:
                    out.append("?")
                i += 5
                escaped = False
                continue
            out.append(escapes.get(ch, ch))
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == '"':
            return "".join(out), True
        else:
            out.append(ch)
        i += 1
    return "".join(out), False


async def chat_json(
    *,
    level: str,
    scenario: str,
    user_text: str,
    history: list[dict[str, str]],
    teacher_persona: str = "A friendly English teacher.",
    goal: str = "Practice a short English conversation.",
    recommended_words: list[str] | None = None,
    turn_index: int = 0,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """非流式调用；解析失败由上层决定重试/降级。"""
    s = get_settings()
    if not s.ark_api_key:
        raise RuntimeError("ARK_API_KEY is not configured")

    system_prompt = build_teacher_system_prompt(
        level=level,
        scenario_title=scenario,
        teacher_persona=teacher_persona,
        goal=goal,
        recommended_words=recommended_words,
        history=history,
        turn_index=turn_index,
    )
    payload: dict[str, Any] = {
        "model": s.ark_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": build_user_prompt(scenario, user_text)},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(75.0, connect=15.0)) as client:
        resp = await client.post(
            f"{s.ark_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {s.ark_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    content = data["choices"][0]["message"]["content"]
    raw = json.loads(_strip_json_fence(content))
    normalized = normalize_teacher_payload(raw, user_text)
    normalized["usage"] = data.get("usage", {})
    normalized["raw_model"] = data.get("model", s.ark_model)
    return normalized


async def stream_teacher_turn(**kwargs):
    """Yield ("delta", str)，最后 yield ("final", normalized dict)。"""
    s = get_settings()
    if not s.ark_api_key:
        raise RuntimeError("ARK_API_KEY is not configured")

    temperature = kwargs.pop("temperature", 0.3)
    user_text = kwargs.pop("user_text")
    build_kwargs = dict(kwargs)
    build_kwargs["scenario_title"] = build_kwargs.pop("scenario")
    system_prompt = build_teacher_system_prompt(**build_kwargs)
    payload = {
        "model": s.ark_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": build_user_prompt(kwargs["scenario"], user_text)},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    parser = _JsonStringStreamParser("teacher_reply")
    usage: dict[str, int] = {}
    buffer = ""
    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=15.0)) as client:
        async with client.stream(
            "POST",
            f"{s.ark_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {s.ark_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                event = json.loads(data)
                if event.get("usage"):
                    usage = event["usage"]
                choices = event.get("choices") or []
                if not choices:
                    continue
                content = (choices[0].get("delta") or {}).get("content")
                if not content:
                    continue
                buffer += content
                delta = parser.feed(content)
                if delta:
                    yield "delta", delta

    raw = json.loads(_strip_json_fence(buffer))
    normalized = normalize_teacher_payload(raw, user_text)
    normalized["usage"] = usage
    normalized["raw_model"] = s.ark_model
    yield "final", normalized


async def generate_conversation_report(
    *,
    level: str,
    scenario_title: str,
    summary: dict[str, Any],
) -> dict[str, Any]:
    """结束后的鼓励式老师总评；外层负责在失败时用确定性兜底。"""
    s = get_settings()
    system_prompt = f"""You are an encouraging English teacher. Write a short report for a {level} student after the scenario '{scenario_title}'.
Be specific but kind. Keep each Chinese tip under 30 Chinese characters. Return only JSON."""
    user_prompt = json.dumps(
        {
            "task": "Write a concise conversation report.",
            "stats": {
                "total_sentences": summary.get("total_sentences"),
                "error_sentences": summary.get("error_sentences"),
                "kind_counts": summary.get("kind_counts"),
                "corrections": summary.get("corrections", [])[:8],
            },
            "schema": {
                "encouragement_en": "one short English sentence",
                "encouragement_zh": "一句中文鼓励",
                "next_tips": ["3 short Chinese study tips"],
            },
        },
        ensure_ascii=False,
    )
    payload = {
        "model": s.ark_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
        resp = await client.post(
            f"{s.ark_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {s.ark_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    raw = json.loads(_strip_json_fence(data["choices"][0]["message"]["content"]))
    tips = raw.get("next_tips") if isinstance(raw.get("next_tips"), list) else []
    return {
        "encouragement_en": _clean_report_text(raw.get("encouragement_en"), 240),
        "encouragement_zh": _clean_report_text(raw.get("encouragement_zh"), 240),
        "next_tips": [_clean_report_text(x, 120) for x in tips[:3] if _clean_report_text(x, 120)],
        "usage": data.get("usage", {}),
        "raw_model": data.get("model", s.ark_model),
    }


def _clean_report_text(value: Any, max_len: int) -> str:
    text = str(value or "").strip()
    return text[:max_len]
