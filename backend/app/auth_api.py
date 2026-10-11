"""手机号一键进入（无验证码，新号带昵称自动注册）。"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.security import create_access_token, verify_password
from app.db import SessionLocal
from app.deps import get_current_user
from app.models import User

router = APIRouter(prefix="/api/v1/auth")

_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
LEVELS = {"junior-g7", "junior", "senior", "cet4", "cet6", "ielts"}


class PhoneAuthRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=32)
    display_name: str | None = Field(default=None, min_length=1, max_length=32)


class MePatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=32)
    level: str | None = None
    daily_new_goal: int | None = Field(default=None, ge=0, le=100)


def user_out(u: User) -> dict:
    return {
        "id": u.id,
        "phone": u.phone,
        "email": u.email,
        "display_name": u.display_name,
        "role": u.role,
        "level": u.level,
        "daily_new_goal": u.daily_new_goal,
    }


def token_for(u: User) -> dict:
    return {"token": create_access_token(u.id, u.role), "user": user_out(u)}


@router.post("/phone")
def phone_auth(req: PhoneAuthRequest):
    phone = req.phone.strip()
    if not _PHONE_RE.match(phone):
        raise HTTPException(status_code=400, detail="请输入正确的 11 位手机号")
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.phone == phone))
        if user is not None:
            if not user.is_active:
                raise HTTPException(status_code=403, detail="账号已停用")
            return token_for(user)
        name = (req.display_name or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="首次进入请填写昵称")
        user = User(phone=phone, display_name=name, role="user")
        db.add(user)
        db.commit()
        db.refresh(user)
        return token_for(user)
    finally:
        db.close()


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.patch("/me")
def update_me(
    req: MePatch, user: User = Depends(get_current_user)
):
    if req.level is not None and req.level not in LEVELS:
        raise HTTPException(status_code=400, detail="未知级别")
    db = SessionLocal()
    try:
        u = db.get(User, user.id)
        if req.display_name:
            u.display_name = req.display_name
        if req.level:
            u.level = req.level
        if req.daily_new_goal is not None:
            u.daily_new_goal = req.daily_new_goal
        db.commit()
        db.refresh(u)
        return user_out(u)
    finally:
        db.close()
