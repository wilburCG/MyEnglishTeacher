from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app import audio_api, auth_api, content_api, conversation_api, dictation_api, learn_api
from app.config import get_settings
from app.db import Base, engine
from app.models import (  # noqa: F401
    ContentFavorite,
    Conversation,
    ConversationMessage,
    DictationAttempt,
    LlmCallLog,
    MovieLine,
    ReviewItem,
    Scenario,
    SentencePattern,
    User,
    UserWordState,
    Word,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # M1 开发期直接建表；后续里程碑引入 alembic 迁移
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="MyEnglishTeacher API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_api.router)
app.include_router(learn_api.router)
app.include_router(audio_api.router)
app.include_router(content_api.router)
app.include_router(content_api.admin_router)
app.include_router(conversation_api.router)
app.include_router(dictation_api.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "met-backend", "env": settings.app_env}


@app.get("/api/v1/health")
def api_health():
    db_ok = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    except Exception as exc:  # noqa: BLE001
        db_ok = f"error: {type(exc).__name__}"
    return {"status": "ok", "db": db_ok, "model": settings.ark_model}
