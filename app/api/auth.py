# app/api/auth.py
from __future__ import annotations
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.schemas import TokenOut, UserOut
from app.auth.jwt import create_token
from app.auth.passwords import hash_password, verify_password
from app.auth.deps import current_user
from app.config import get_settings
from app.db.session import get_db
from app.db.models import User, Role

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


class SignupIn(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


def _validate_username(s: str) -> None:
    if not _USERNAME_RE.match(s):
        raise HTTPException(
            status_code=400,
            detail="username must be 3-32 chars, letters/digits/._- only",
        )


@router.post("/signup", response_model=TokenOut)
def signup(body: SignupIn, db: Session = Depends(get_db)):
    """Public self-registration. Creates a user with role=user and returns a JWT.

    Email and username must be unique. Password is bcrypt-hashed.
    """
    _validate_username(body.username)
    if db.query(User).filter_by(username=body.username).first():
        raise HTTPException(status_code=409, detail="username already taken")
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(status_code=409, detail="email already registered")

    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
        role=Role.user,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    tok = create_token(user.id, user.role.value)
    return TokenOut(access_token=tok, expires_in=get_settings().jwt_expires_min * 60)


@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    u = db.query(User).filter_by(username=form.username, is_active=True).first()
    if not u or not verify_password(form.password, u.password_hash):
        raise HTTPException(status_code=401, detail="bad credentials")
    u.last_login_at = datetime.now(timezone.utc)
    db.commit()
    tok = create_token(u.id, u.role.value)
    return TokenOut(access_token=tok, expires_in=get_settings().jwt_expires_min * 60)


@router.get("/me", response_model=UserOut)
def me(u: User = Depends(current_user)):
    return UserOut(id=u.id, username=u.username, email=u.email, role=u.role.value)