"""M3 AI 场景对话：场景卡、SSE 流式老师回复、结构化纠错、报告、复习本。"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select

from app.config import get_settings
from app.core.corrections import safe_teacher_fallback, summarize_conversation
from app.core.llm import chat_json, generate_conversation_report, stream_teacher_turn
from app.db import SessionLocal
from app.deps import get_current_user
from app.models import (
    Conversation,
    ConversationMessage,
    LlmCallLog,
    ReviewItem,
    Scenario,
    User,
)

router = APIRouter(prefix="/api/v1", tags=["conversation"])
CN_TZ = timezone(timedelta(hours=8))
MAX_MESSAGE_LEN = 500
MAX_CONVERSATION_TURNS = 30

KIND_ZH = {
    "grammar": "语法",
    "tense": "时态",
    "spelling": "拼写",
    "vocabulary": "用词",
    "collocation": "搭配/介词",
    "word_order": "语序",
    "pragmatics": "语境表达",
}


def now_cn() -> datetime:
    return datetime.now(CN_TZ)


def aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def scenario_out(s: Scenario) -> dict[str, Any]:
    return {
        "id": s.id,
        "level": s.level,
        "theme": s.theme,
        "title_en": s.title_en,
        "title_zh": s.title_zh,
        "description_zh": s.description_zh,
        "goal": s.goal,
        "opening_line": s.opening_line,
        "recommended_words": s.recommended_words or [],
        "difficulty": s.difficulty,
    }


def message_out(m: ConversationMessage) -> dict[str, Any]:
    return {
        "id": m.id,
        "conversation_id": m.conversation_id,
        "role": m.role,
        "content": m.content,
        "has_error": m.has_error,
        "corrections": m.corrections or [],
        "better_version": m.better_version or "",
        "hint_zh": m.hint_zh or "",
        "model_validated": m.model_validated,
        "created_at": aware(m.created_at).isoformat() if m.created_at else None,
    }


def conversation_out(c: Conversation, scenario: Scenario | None = None) -> dict[str, Any]:
    return {
        "id": c.id,
        "scenario_id": c.scenario_id,
        "level": c.level,
        "theme": c.theme,
        "title_en": c.title_en,
        "title_zh": c.title_zh,
        "status": c.status,
        "turn_count": c.turn_count,
        "report": c.report,
        "started_at": aware(c.started_at).isoformat() if c.started_at else None,
        "ended_at": aware(c.ended_at).isoformat() if c.ended_at else None,
        "scenario": scenario_out(scenario) if scenario else None,
    }


def get_owned_conversation(db, conversation_id: int, user: User) -> Conversation:
    c = db.get(Conversation, conversation_id)
    if c is None or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="对话不存在")
    return c


def get_scenario(db, scenario_id: int) -> Scenario:
    s = db.get(Scenario, scenario_id)
    if s is None or not s.is_published:
        raise HTTPException(status_code=404, detail="场景不存在或未发布")
    return s


def history_for_llm(messages: list[ConversationMessage]) -> list[dict[str, str]]:
    return [
        {"role": "user" if m.role == "user" else "assistant", "content": m.content}
        for m in messages
        if m.role in ("user", "assistant")
    ]


def llm_kwargs(scenario: Scenario, conversation: Conversation, user_text: str,
               messages: list[ConversationMessage]) -> dict[str, Any]:
    return {
        "level": conversation.level,
        "scenario": scenario.title_en,
        "teacher_persona": scenario.teacher_persona,
        "goal": scenario.goal,
        "recommended_words": scenario.recommended_words or [],
        "history": history_for_llm(messages),
        "turn_index": conversation.turn_count,
        "user_text": user_text,
    }


def usage_values(usage: dict[str, Any] | None) -> tuple[int, int, int]:
    usage = usage or {}
    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    total = int(usage.get("total_tokens") or (prompt + completion))
    return prompt, completion, total


def write_log(db, *, user_id: int, feature: str, conversation_id: int | None,
              model: str, latency_ms: int, usage: dict[str, Any] | None,
              success: bool, error: str = "") -> LlmCallLog:
    prompt, completion, total = usage_values(usage)
    row = LlmCallLog(
        user_id=user_id,
        feature=feature,
        model=model or get_settings().ark_model,
        conversation_id=conversation_id,
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        cost_amount=None,
        latency_ms=latency_ms,
        success=success,
        error=error[:2000] if error else None,
    )
    db.add(row)
    db.flush()
    return row


def check_daily_quota(db, user: User) -> None:
    start = now_cn().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    total = db.scalar(
        select(func.count())
        .select_from(ConversationMessage)
        .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
        .where(
            and_(
                Conversation.user_id == user.id,
                ConversationMessage.role == "user",
                ConversationMessage.created_at >= start,
                ConversationMessage.created_at < end,
            )
        )
    )
    if total >= get_settings().daily_dialogue_turns:
        raise HTTPException(status_code=429, detail="今日对话轮次已达上限，明天再来吧")


async def call_teacher_with_retry(kwargs: dict[str, Any]) -> tuple[dict[str, Any], bool, str]:
    try:
        return await chat_json(**kwargs), True, ""
    except Exception as first:  # noqa: BLE001
        try:
            return await chat_json(**{**kwargs, "temperature": 0.0}), True, ""
        except Exception as second:  # noqa: BLE001
            fallback = safe_teacher_fallback(kwargs["user_text"])
            return fallback, False, f"{type(first).__name__}: {first}; retry: {second}"


def persist_turn(db, *, conversation: Conversation, scenario: Scenario,
                 user_text: str, result: dict[str, Any], latency_ms: int,
                 success: bool, error: str) -> dict[str, Any]:
    user_msg = ConversationMessage(
        conversation_id=conversation.id,
        role="user",
        content=user_text,
        has_error=bool(result.get("corrections")),
        corrections=result.get("corrections") or [],
        better_version=result.get("better_version") or "",
        hint_zh="",
        model_validated=bool(result.get("model_validated")),
    )
    db.add(user_msg)
    db.flush()

    log = write_log(
        db,
        user_id=conversation.user_id,
        feature="conversation_turn",
        conversation_id=conversation.id,
        model=str(result.get("raw_model") or get_settings().ark_model),
        latency_ms=latency_ms,
        usage=result.get("usage") if isinstance(result.get("usage"), dict) else {},
        success=success,
        error=error,
    )
    assistant_msg = ConversationMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=result["teacher_reply"],
        has_error=None,
        corrections=None,
        better_version="",
        hint_zh=result.get("hint_zh") or "",
        model_validated=bool(result.get("model_validated")),
        llm_call_log_id=log.id,
    )
    db.add(assistant_msg)
    conversation.turn_count += 1
    db.flush()
    return {"user_message": message_out(user_msg), "assistant_message": message_out(assistant_msg)}


class StartConversationIn(BaseModel):
    scenario_id: int


class TurnIn(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_MESSAGE_LEN)


class SaveReviewIn(BaseModel):
    message_id: int | None = None
    correction_index: int | None = None
    save_all: bool = False


class ReviewPatchIn(BaseModel):
    is_resolved: bool | None = None


@router.get("/scenarios")
def list_scenarios(include_all_levels: bool = False, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        stmt = select(Scenario).where(Scenario.is_published.is_(True))
        if not include_all_levels:
            stmt = stmt.where(Scenario.level == user.level)
        rows = db.scalars(stmt.order_by(Scenario.seq.asc(), Scenario.id.asc())).all()
        if not rows and not include_all_levels:
            rows = db.scalars(
                select(Scenario)
                .where(and_(Scenario.is_published.is_(True), Scenario.level == "junior-g7"))
                .order_by(Scenario.seq.asc())
            ).all()
        return {"scenarios": [scenario_out(s) for s in rows]}
    finally:
        db.close()


@router.post("/conversations")
def start_conversation(req: StartConversationIn, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        scenario = get_scenario(db, req.scenario_id)
        conv = Conversation(
            user_id=user.id,
            scenario_id=scenario.id,
            level=scenario.level,
            theme=scenario.theme,
            title_en=scenario.title_en,
            title_zh=scenario.title_zh,
            status="active",
        )
        db.add(conv)
        db.flush()
        db.add(
            ConversationMessage(
                conversation_id=conv.id,
                role="assistant",
                content=scenario.opening_line,
                model_validated=True,
            )
        )
        db.commit()
        db.refresh(conv)
        return conversation_out(conv, scenario)
    finally:
        db.close()


@router.get("/conversations")
def list_conversations(user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.started_at.desc())
            .limit(50)
        ).all()
        scenarios = {s.id: s for s in db.scalars(select(Scenario)).all()}
        return {"conversations": [conversation_out(c, scenarios.get(c.scenario_id)) for c in rows]}
    finally:
        db.close()


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: int, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        conv = get_owned_conversation(db, conversation_id, user)
        scenario = db.get(Scenario, conv.scenario_id)
        msgs = db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conv.id)
            .order_by(ConversationMessage.created_at.asc(), ConversationMessage.id.asc())
        ).all()
        return {
            "conversation": conversation_out(conv, scenario),
            "messages": [message_out(m) for m in msgs],
            "kind_zh": KIND_ZH,
        }
    finally:
        db.close()


@router.post("/conversations/{conversation_id}/messages")
async def send_message(conversation_id: int, req: TurnIn, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        user_text = req.text.strip()
        if not user_text:
            raise HTTPException(status_code=400, detail="请输入英文句子")
        check_daily_quota(db, user)
        conv = get_owned_conversation(db, conversation_id, user)
        if conv.status != "active":
            raise HTTPException(status_code=409, detail="这场对话已结束")
        if conv.turn_count >= MAX_CONVERSATION_TURNS:
            raise HTTPException(status_code=409, detail="单场对话轮次已达上限，请生成报告")
        scenario = get_scenario(db, conv.scenario_id)
        msgs = db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conv.id)
            .order_by(ConversationMessage.created_at.asc(), ConversationMessage.id.asc())
        ).all()
        started = time.monotonic()
        result, success, error = await call_teacher_with_retry(
            llm_kwargs(scenario, conv, user_text, list(msgs))
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        out = persist_turn(
            db,
            conversation=conv,
            scenario=scenario,
            user_text=user_text,
            result=result,
            latency_ms=latency_ms,
            success=success,
            error=error,
        )
        db.commit()
        return {"turn": out, "kind_zh": KIND_ZH}
    finally:
        db.close()


def sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/conversations/{conversation_id}/messages/stream")
async def stream_message(conversation_id: int, req: TurnIn, user: User = Depends(get_current_user)):
    # 在 StreamingResponse 外先完成权限/配额检查，让错误以普通 HTTP 状态返回。
    db0 = SessionLocal()
    try:
        user_text = req.text.strip()
        if not user_text:
            raise HTTPException(status_code=400, detail="请输入英文句子")
        check_daily_quota(db0, user)
        conv0 = get_owned_conversation(db0, conversation_id, user)
        if conv0.status != "active":
            raise HTTPException(status_code=409, detail="这场对话已结束")
        if conv0.turn_count >= MAX_CONVERSATION_TURNS:
            raise HTTPException(status_code=409, detail="单场对话轮次已达上限，请生成报告")
        scenario0 = get_scenario(db0, conv0.scenario_id)
        history = db0.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conv0.id)
            .order_by(ConversationMessage.created_at.asc(), ConversationMessage.id.asc())
        ).all()
        kwargs = llm_kwargs(scenario0, conv0, user_text, list(history))
    finally:
        db0.close()

    async def generate():
        db = SessionLocal()
        started = time.monotonic()
        final_result: dict[str, Any] | None = None
        stream_ok = False
        stream_error = ""
        try:
            async for event_name, data in stream_teacher_turn(**kwargs):
                if event_name == "delta":
                    yield sse("delta", {"text": data})
                elif event_name == "final":
                    final_result = data
                    stream_ok = True
        except Exception as exc:  # noqa: BLE001
            stream_error = f"{type(exc).__name__}: {exc}"
            final_result = safe_teacher_fallback(user_text)

        try:
            conv = get_owned_conversation(db, conversation_id, user)
            scenario = get_scenario(db, conv.scenario_id)
            latency_ms = int((time.monotonic() - started) * 1000)
            out = persist_turn(
                db,
                conversation=conv,
                scenario=scenario,
                user_text=user_text,
                result=final_result or safe_teacher_fallback(user_text),
                latency_ms=latency_ms,
                success=stream_ok,
                error=stream_error,
            )
            db.commit()
            yield sse("final", {"turn": out, "kind_zh": KIND_ZH})
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            yield sse("error", {"detail": f"保存失败：{type(exc).__name__}"})
        finally:
            db.close()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/conversations/{conversation_id}/finish")
async def finish_conversation(conversation_id: int, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        conv = get_owned_conversation(db, conversation_id, user)
        scenario = db.get(Scenario, conv.scenario_id)
        if conv.status == "finished" and conv.report:
            return {"report": conv.report}

        msgs = db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conv.id)
            .order_by(ConversationMessage.created_at.asc(), ConversationMessage.id.asc())
        ).all()
        message_dicts = [
            {
                "role": m.role,
                "content": m.content,
                "has_error": m.has_error,
                "corrections": m.corrections or [],
            }
            for m in msgs
        ]
        report = summarize_conversation(
            level=conv.level,
            scenario_title=conv.title_en,
            goal=scenario.goal if scenario else "",
            messages=message_dicts,
        )
        started = time.monotonic()
        teacher_report = None
        success = False
        error = ""
        usage: dict[str, Any] = {}
        model = get_settings().ark_model
        try:
            teacher_report = await generate_conversation_report(
                level=conv.level, scenario_title=conv.title_en, summary=report
            )
            usage = teacher_report.pop("usage", {}) or {}
            model = teacher_report.pop("raw_model", model)
            success = bool(teacher_report.get("encouragement_zh"))
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"

        if not teacher_report:
            teacher_report = {
                "encouragement_en": "Great practice! Review your errors and try the scenario again.",
                "encouragement_zh": "完成练习很棒！先复习错句，再挑战一次会更熟练。",
                "next_tips": ["先读熟修改后的句子", "注意错误类型最多的语法点", "明天再复习一次"],
            }
        report["teacher"] = teacher_report
        conv.status = "finished"
        conv.ended_at = now_cn()
        conv.report = report
        write_log(
            db,
            user_id=user.id,
            feature="conversation_report",
            conversation_id=conv.id,
            model=model,
            latency_ms=int((time.monotonic() - started) * 1000),
            usage=usage,
            success=success,
            error=error,
        )
        db.commit()
        return {"report": report, "kind_zh": KIND_ZH}
    finally:
        db.close()


def _correction_records(db, conv: Conversation, req: SaveReviewIn):
    user_msgs = db.scalars(
        select(ConversationMessage)
        .where(
            and_(
                ConversationMessage.conversation_id == conv.id,
                ConversationMessage.role == "user",
            )
        )
        .order_by(ConversationMessage.id.asc())
    ).all()
    records = []
    if not req.save_all:
        if req.message_id is None or req.correction_index is None:
            raise HTTPException(status_code=400, detail="缺少要保存的纠错")
        msg = next((m for m in user_msgs if m.id == req.message_id), None)
        if msg is None:
            raise HTTPException(status_code=404, detail="消息不存在")
        corrections = msg.corrections or []
        if req.correction_index >= len(corrections):
            raise HTTPException(status_code=404, detail="纠错不存在")
        records.append((msg, corrections[req.correction_index]))
    else:
        for msg in user_msgs:
            for c in msg.corrections or []:
                records.append((msg, c))
    return records


def review_item_out(item: ReviewItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "source_type": item.source_type,
        "source_conversation_id": item.source_conversation_id,
        "source_message_id": item.source_message_id,
        "item_kind": item.item_kind,
        "kind_zh": KIND_ZH.get(item.item_kind or "", item.item_kind),
        "title": item.title,
        "original": item.original,
        "corrected": item.corrected,
        "explanation_zh": item.explanation_zh,
        "context_sentence": item.context_sentence,
        "wrong_count": item.wrong_count,
        "is_resolved": item.is_resolved,
        "created_at": aware(item.created_at).isoformat() if item.created_at else None,
    }


@router.post("/conversations/{conversation_id}/review-items")
def save_review_items(conversation_id: int, req: SaveReviewIn, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        conv = get_owned_conversation(db, conversation_id, user)
        records = _correction_records(db, conv, req)
        saved = []
        for msg, c in records:
            existing = db.scalar(
                select(ReviewItem).where(
                    and_(
                        ReviewItem.user_id == user.id,
                        ReviewItem.source_type == "conversation_error",
                        ReviewItem.source_message_id == msg.id,
                        ReviewItem.original == c.get("original", ""),
                    )
                )
            )
            if existing is None:
                existing = ReviewItem(
                    user_id=user.id,
                    source_type="conversation_error",
                    source_conversation_id=conv.id,
                    source_message_id=msg.id,
                    item_kind=c.get("kind", "grammar"),
                    title=conv.title_zh,
                    original=c.get("original", ""),
                    corrected=c.get("corrected", ""),
                    explanation_zh=c.get("explanation_zh", ""),
                    context_sentence=msg.content,
                    due_at=now_cn(),
                )
                db.add(existing)
                db.flush()
            saved.append(existing)
        db.commit()
        return {"saved": [review_item_out(x) for x in saved], "count": len(saved)}
    finally:
        db.close()


@router.get("/review-items")
def list_review_items(include_resolved: bool = False, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        stmt = select(ReviewItem).where(ReviewItem.user_id == user.id)
        if not include_resolved:
            stmt = stmt.where(ReviewItem.is_resolved.is_(False))
        rows = db.scalars(stmt.order_by(ReviewItem.created_at.desc()).limit(200)).all()
        return {"items": [review_item_out(x) for x in rows], "kind_zh": KIND_ZH}
    finally:
        db.close()


@router.patch("/review-items/{item_id}")
def patch_review_item(item_id: int, req: ReviewPatchIn, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        item = db.get(ReviewItem, item_id)
        if item is None or item.user_id != user.id:
            raise HTTPException(status_code=404, detail="复习项不存在")
        if req.is_resolved is not None:
            item.is_resolved = req.is_resolved
        db.commit()
        return review_item_out(item)
    finally:
        db.close()


@router.delete("/review-items/{item_id}")
def delete_review_item(item_id: int, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        item = db.get(ReviewItem, item_id)
        if item is None or item.user_id != user.id:
            raise HTTPException(status_code=404, detail="复习项不存在")
        db.delete(item)
        db.commit()
        return {"ok": True}
    finally:
        db.close()
