from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.db import engine

settings = get_settings()

app = FastAPI(title="MyEnglishTeacher API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "met-backend", "env": settings.app_env}


@app.get("/api/v1/health")
async def api_health() -> dict[str, str]:
    db_ok = "ok"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
    except Exception as exc:  # noqa: BLE001
        db_ok = f"error: {type(exc).__name__}"
    return {"status": "ok", "db": db_ok, "model": settings.ark_model}
