# tests/integration/test_api_history.py
from __future__ import annotations

import json

import ulid


def _make_job(*, user_id: int, kind: str = "t2v", model_id: str = "ltx-2b-distilled") -> str:
    """Insert a queued Job row directly so it appears in the user's history."""
    from app.db.session import SessionLocal
    from app.db.models import Job

    job_id = str(ulid.ULID())
    with SessionLocal() as db:
        db.add(
            Job(
                id=job_id,
                user_id=user_id,
                kind=kind,
                model_id=model_id,
                params_json=json.dumps({"prompt": "x"}),
            )
        )
        db.commit()
    return job_id


def _admin_user_id(client) -> int:
    from app.db.session import SessionLocal
    from app.db.models import User

    with SessionLocal() as db:
        u = db.query(User).filter_by(username="admin").first()
        return u.id


def test_history_empty_initially(client, auth_headers):
    r = client.get("/api/v1/history", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_history_delete_removes_row(client, auth_headers):
    user_id = _admin_user_id(client)
    job_id = _make_job(user_id=user_id)

    # The new job should appear in history.
    r = client.get("/api/v1/history", headers=auth_headers)
    assert r.status_code == 200
    ids = [item["id"] for item in r.json()]
    assert job_id in ids

    # Delete it and confirm 200 + row gone.
    r = client.delete(f"/api/v1/history/{job_id}", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}

    r = client.get("/api/v1/history", headers=auth_headers)
    assert r.status_code == 200
    assert all(item["id"] != job_id for item in r.json())


def test_history_delete_missing_404(client, auth_headers):
    r = client.delete("/api/v1/history/01HFAKE0000000000000000000", headers=auth_headers)
    assert r.status_code == 404