# app/auth/jwt.py
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from app.config import get_settings


class TokenError(Exception):
    pass


def create_token(user_id: int, role: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.jwt_expires_min)).timestamp()),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=["HS256"])
    except JWTError as e:
        raise TokenError(str(e)) from e
