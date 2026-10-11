from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(128), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(256))
    display_name: Mapped[str] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(16), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # junior-g7 / junior / senior / cet4 / cet6 / ielts
    level: Mapped[str] = mapped_column(String(16), default="junior-g7", index=True)
    daily_new_goal: Mapped[int] = mapped_column(Integer, default=10)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Word(Base):
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    headword: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    phonetic: Mapped[str | None] = mapped_column(String(128))
    pos: Mapped[str | None] = mapped_column(String(128))
    definition_en: Mapped[str | None] = mapped_column(Text)
    translation: Mapped[str | None] = mapped_column(Text)
    tag: Mapped[str | None] = mapped_column(String(128))

    level: Mapped[str] = mapped_column(String(16), index=True)
    unit: Mapped[str | None] = mapped_column(String(32))
    seq: Mapped[int] = mapped_column(Integer, default=0, index=True)

    frq: Mapped[int | None] = mapped_column(Integer)
    bnc: Mapped[int | None] = mapped_column(Integer)
    collins: Mapped[int | None] = mapped_column(Integer)
    oxford: Mapped[int | None] = mapped_column(Integer)
    examples: Mapped[list | None] = mapped_column(JSON)

    states: Mapped[list["UserWordState"]] = relationship(back_populates="word")


class UserWordState(Base):
    __tablename__ = "user_word_state"
    __table_args__ = (
        UniqueConstraint("user_id", "word_id", name="uq_user_word"),
        Index("ix_state_due", "user_id", "due_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    word_id: Mapped[int] = mapped_column(
        ForeignKey("words.id", ondelete="CASCADE"), index=True
    )

    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[int] = mapped_column(Integer, default=0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    introduced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)

    word: Mapped[Word] = relationship(back_populates="states")


class ReviewLog(Base):
    __tablename__ = "review_log"
    __table_args__ = (Index("ix_log_user_time", "user_id", "reviewed_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"))

    # 0=不认识(again) 1=模糊(hard) 2=认识(good) 3=很熟(easy)
    grade: Mapped[int] = mapped_column(Integer)
    # card=卡片复习，dictation=听写
    kind: Mapped[str] = mapped_column(String(16), default="card")
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    interval_days: Mapped[int] = mapped_column(Integer, default=0)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class SentencePattern(Base):
    """典型句型：模板 + 功能 + 语法点 + 分级例句。"""

    __tablename__ = "sentence_pattern"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(16), index=True)
    theme: Mapped[str] = mapped_column(String(32), index=True)
    unit: Mapped[str | None] = mapped_column(String(32))
    seq: Mapped[int] = mapped_column(Integer, default=0, index=True)

    template: Mapped[str] = mapped_column(String(256))
    func_zh: Mapped[str] = mapped_column(String(256))
    grammar_point: Mapped[str | None] = mapped_column(String(128))
    explanation_zh: Mapped[str | None] = mapped_column(Text)
    # [{"en": "...", "zh": "..."}]
    examples: Mapped[list] = mapped_column(JSON)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class MovieLine(Base):
    """影视剧台词（M2 旗舰：Friends 老友记，短句精选 + 出处署名）。"""

    __tablename__ = "movie_line"
    __table_args__ = (Index("ix_line_show", "show", "season", "episode"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    show: Mapped[str] = mapped_column(String(64), default="Friends", index=True)
    season: Mapped[int | None] = mapped_column(Integer)
    episode: Mapped[int | None] = mapped_column(Integer)
    character: Mapped[str] = mapped_column(String(64), index=True)

    text_en: Mapped[str] = mapped_column(Text)
    text_zh: Mapped[str] = mapped_column(Text)
    level: Mapped[str] = mapped_column(String(16), index=True)
    theme: Mapped[str | None] = mapped_column(String(32), index=True)
    note_zh: Mapped[str | None] = mapped_column(Text)

    seq: Mapped[int] = mapped_column(Integer, default=0, index=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class ContentFavorite(Base):
    """句型 / 台词收藏（单词收藏沿用 user_word_state.is_favorite）。"""

    __tablename__ = "content_favorite"
    __table_args__ = (
        UniqueConstraint("user_id", "item_type", "item_id", name="uq_cfav"),
        Index("ix_cfav_user", "user_id", "item_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    item_type: Mapped[str] = mapped_column(String(16))  # pattern / line
    item_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Scenario(Base):
    """AI 对话场景卡。"""

    __tablename__ = "scenario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(16), index=True)
    theme: Mapped[str] = mapped_column(String(32), index=True)
    title_en: Mapped[str] = mapped_column(String(128))
    title_zh: Mapped[str] = mapped_column(String(128))
    description_zh: Mapped[str | None] = mapped_column(Text)
    teacher_persona: Mapped[str] = mapped_column(Text)
    goal: Mapped[str] = mapped_column(Text)
    opening_line: Mapped[str] = mapped_column(Text)
    recommended_words: Mapped[list] = mapped_column(JSON, default=list)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    seq: Mapped[int] = mapped_column(Integer, default=0, index=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Conversation(Base):
    """一场学生与 AI 老师的场景对话。"""

    __tablename__ = "conversation"
    __table_args__ = (Index("ix_conv_user_status", "user_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenario.id", ondelete="RESTRICT"), index=True
    )

    level: Mapped[str] = mapped_column(String(16), index=True)
    theme: Mapped[str | None] = mapped_column(String(32))
    title_en: Mapped[str] = mapped_column(String(128))
    title_zh: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    report: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConversationMessage(Base):
    """对话消息；用户消息上挂载结构化纠错。"""

    __tablename__ = "conversation_message"
    __table_args__ = (Index("ix_cmsg_conv", "conversation_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversation.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user / assistant / system
    content: Mapped[str] = mapped_column(Text)

    has_error: Mapped[bool | None] = mapped_column(Boolean)
    corrections: Mapped[list | None] = mapped_column(JSON)
    better_version: Mapped[str | None] = mapped_column(Text)
    hint_zh: Mapped[str | None] = mapped_column(Text)
    model_validated: Mapped[bool | None] = mapped_column(Boolean)
    llm_call_log_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class ReviewItem(Base):
    """统一错词/错句复习本（M3 先收藏对话纠错，M4 接听写与 SRS）。"""

    __tablename__ = "review_item"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_type",
            "source_message_id",
            "original",
            name="uq_review_item",
        ),
        Index("ix_review_user", "user_id", "is_resolved", "due_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(32), default="conversation_error")
    source_conversation_id: Mapped[int | None] = mapped_column(Integer)
    source_message_id: Mapped[int | None] = mapped_column(Integer)

    item_kind: Mapped[str | None] = mapped_column(String(32))
    title: Mapped[str | None] = mapped_column(String(256))
    original: Mapped[str] = mapped_column(Text)
    corrected: Mapped[str] = mapped_column(Text)
    explanation_zh: Mapped[str | None] = mapped_column(Text)
    context_sentence: Mapped[str | None] = mapped_column(Text)

    wrong_count: Mapped[int] = mapped_column(Integer, default=1)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LlmCallLog(Base):
    """LLM 调用、token 与延迟审计；先预留成本字段。"""

    __tablename__ = "llm_call_log"
    __table_args__ = (Index("ix_llm_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    feature: Mapped[str] = mapped_column(String(32), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="volcengine-ark")
    model: Mapped[str] = mapped_column(String(128))
    conversation_id: Mapped[int | None] = mapped_column(Integer, index=True)

    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_amount: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
