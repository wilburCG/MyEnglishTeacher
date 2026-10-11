from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_token
from app.db import SessionLocal
from app.models import User

_bearer = HTTPBearer(auto_error=False)


def _resolve(cred: Optional[HTTPAuthorizationCredentials], token_query: str | None):
    raw = cred.credentials if cred is not None else token_query
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录"
        )
    try:
        payload = decode_token(raw)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效，请重新登录"
        )
    db = SessionLocal()
    try:
        user = db.get(User, int(payload["sub"]))
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已停用"
            )
        return user
    finally:
        db.close()


def get_current_user(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    t: Optional[str] = None,
) -> User:
    return _resolve(cred, t)
