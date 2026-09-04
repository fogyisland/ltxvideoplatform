# app/api/auth.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.schemas import LoginIn, TokenOut, UserOut
from app.auth.jwt import create_token
from app.auth.passwords import verify_password
from app.auth.deps import current_user
from app.config import get_settings
from app.db.session import get_db
from app.db.models import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    u = db.query(User).filter_by(username=form.username, is_active=True).first()
    if not u or not verify_password(form.password, u.password_hash):
        raise HTTPException(status_code=401, detail="bad credentials")
    tok = create_token(u.id, u.role.value)
    return TokenOut(access_token=tok, expires_in=get_settings().jwt_expires_min * 60)


@router.get("/me", response_model=UserOut)
def me(u: User = Depends(current_user)):
    return UserOut(id=u.id, username=u.username, role=u.role.value)
