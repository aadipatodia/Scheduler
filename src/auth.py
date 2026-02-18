"""
Authentication utilities: phone-number-based identity with cookie session.
No passwords, no registration — just enter your phone number.
"""
import hashlib
import hmac
import json
import os
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import User

SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "change-me-in-production-please")
COOKIE_NAME = "session"


def _sign(payload: str) -> str:
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def _unsign(cookie: str) -> Optional[str]:
    if "." not in cookie:
        return None
    payload, sig = cookie.rsplit(".", 1)
    expected = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    return payload


def create_session_value(user_id: int) -> str:
    return _sign(json.dumps({"uid": user_id}))


def read_session_value(cookie: str) -> Optional[int]:
    payload = _unsign(cookie)
    if payload is None:
        return None
    try:
        data = json.loads(payload)
        return data.get("uid")
    except (json.JSONDecodeError, TypeError):
        return None


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = read_session_value(cookie)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    return user
