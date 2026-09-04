# tests/integration/test_api_admin.py
"""Integration tests for /api/v1/auth/signup and /api/v1/admin/* endpoints."""
import os
import pytest
from fastapi.testclient import TestClient

from app.db.session import Base, get_engine, SessionLocal
from app.db.models import User, Role
from app.auth.passwords import hash_password


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    from app.config import get_settings
    get_settings.cache_clear()
    Base.metadata.drop_all(get_engine())
    Base.metadata.create_all(get_engine())
    with SessionLocal() as s:
        s.add(User(username="admin", email="admin@test.io",
                   password_hash=hash_password("admin"),
                   role=Role.admin, is_active=True))
        s.commit()
    from app.main import build_app
    return TestClient(build_app())


def _token(client):
    r = client.post("/api/v1/auth/login",
                    data={"username": "admin", "password": "admin"})
    return r.json()["access_token"]


def test_signup_creates_user_and_returns_token(client):
    r = client.post("/api/v1/auth/signup", json={
        "username": "alice", "email": "alice@test.io", "password": "secret123"
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert "access_token" in body

    # verify user is in DB with role=user
    with SessionLocal() as s:
        u = s.query(User).filter_by(username="alice").first()
        assert u is not None
        assert u.role == Role.user
        assert u.email == "alice@test.io"
        assert u.is_active


def test_signup_rejects_duplicate_username(client):
    client.post("/api/v1/auth/signup", json={
        "username": "bob", "email": "bob1@test.io", "password": "secret123"
    })
    r = client.post("/api/v1/auth/signup", json={
        "username": "bob", "email": "bob2@test.io", "password": "secret123"
    })
    assert r.status_code == 409


def test_signup_rejects_bad_username(client):
    r = client.post("/api/v1/auth/signup", json={
        "username": "no spaces!", "email": "x@test.io", "password": "secret123"
    })
    assert r.status_code == 400


def test_signup_rejects_short_password(client):
    r = client.post("/api/v1/auth/signup", json={
        "username": "short", "email": "x@test.io", "password": "abc"
    })
    assert r.status_code == 422


def test_admin_users_requires_admin(client):
    # anonymous
    r = client.get("/api/v1/admin/users")
    assert r.status_code == 401
    # regular user (need to create one first)
    client.post("/api/v1/auth/signup", json={
        "username": "carol", "email": "c@test.io", "password": "secret123"
    })
    carol_tok = client.post("/api/v1/auth/login",
                            data={"username": "carol", "password": "secret123"}).json()["access_token"]
    r = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {carol_tok}"})
    assert r.status_code == 403


def test_admin_list_and_create_user(client):
    tok = _token(client)
    h = {"Authorization": f"Bearer {tok}"}
    r = client.get("/api/v1/admin/users", headers=h)
    assert r.status_code == 200
    assert any(u["username"] == "admin" for u in r.json())

    r = client.post("/api/v1/admin/users", json={
        "username": "newby", "email": "newby@test.io", "password": "secret123", "role": "user"
    }, headers=h)
    assert r.status_code == 201
    assert r.json()["username"] == "newby"


def test_admin_cannot_disable_self(client):
    tok = _token(client)
    h = {"Authorization": f"Bearer {tok}"}
    # get admin's own id
    me = client.get("/api/v1/auth/me", headers=h).json()
    r = client.patch(f"/api/v1/admin/users/{me['id']}",
                     json={"is_active": False}, headers=h)
    assert r.status_code == 400


def test_admin_models_endpoint(client):
    tok = _token(client)
    h = {"Authorization": f"Bearer {tok}"}
    r = client.get("/api/v1/admin/models", headers=h)
    assert r.status_code == 200
    rows = r.json()
    assert any(m["id"] == "ltx-2b-distilled" for m in rows)
    assert any("downloaded" in m for m in rows)


def test_admin_stats_endpoint(client):
    tok = _token(client)
    h = {"Authorization": f"Bearer {tok}"}
    r = client.get("/api/v1/admin/stats", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert "gpu" in body and "disk" in body and "users" in body and "jobs" in body


def test_admin_reset_password(client):
    tok = _token(client)
    h = {"Authorization": f"Bearer {tok}"}
    # create a user
    r = client.post("/api/v1/admin/users", json={
        "username": "resetme", "password": "oldpass1", "role": "user"
    }, headers=h)
    uid = r.json()["id"]
    # reset
    r = client.post(f"/api/v1/admin/users/{uid}/reset-password",
                    json={"new_password": "newpass1"}, headers=h)
    assert r.status_code == 204
    # can login with new password
    r = client.post("/api/v1/auth/login",
                    data={"username": "resetme", "password": "newpass1"})
    assert r.status_code == 200