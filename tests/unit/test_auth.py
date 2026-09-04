# tests/unit/test_auth.py
import time
import pytest
from app.auth.passwords import hash_password, verify_password
from app.auth.jwt import create_token, decode_token, TokenError

def test_password_roundtrip():
    h = hash_password("hunter2")
    assert verify_password("hunter2", h)
    assert not verify_password("wrong", h)

def test_jwt_roundtrip():
    tok = create_token(user_id=42, role="admin")
    payload = decode_token(tok)
    assert payload["sub"] == "42"
    assert payload["role"] == "admin"

def test_jwt_invalid_raises():
    with pytest.raises(TokenError):
        decode_token("not.a.token")
