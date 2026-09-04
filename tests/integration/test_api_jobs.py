# tests/integration/test_api_jobs.py
from __future__ import annotations

import json

import ulid


def _make_job(*, user_id: int, kind: str = "t2v", model_id: str = "ltx-2b-distilled") -> str:
    """Insert a queued Job row directly and return its id.

    We bypass the queue/submit machinery so no worker is needed — in the
    test environment the queue thread is never started, so a real submit
    would still leave the row in ``queued`` state. Going straight to the DB
    keeps the test independent of registry loading and other side effects.
    """
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


def test_get_job_requires_auth(client):
    r = client.get("/api/v1/jobs/01HFAKE0000000000000000000")
    assert r.status_code == 401


def test_get_job_404_for_missing(client, auth_headers):
    r = client.get("/api/v1/jobs/01HFAKE0000000000000000000", headers=auth_headers)
    assert r.status_code == 404


def test_get_job_returns_serialized_fields(client, auth_headers):
    job_id = _make_job(user_id=_admin_user_id(client))

    r = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == job_id
    assert body["kind"] == "t2v"
    assert body["status"] == "queued"
    assert body["model_id"] == "ltx-2b-distilled"
    # params round-trip
    assert body["params"] == {"prompt": "x"}


def test_cancel_queued_job(client, auth_headers):
    job_id = _make_job(user_id=_admin_user_id(client))

    r = client.post(f"/api/v1/jobs/{job_id}/cancel", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}


def test_cancel_missing_job_404(client, auth_headers):
    r = client.post("/api/v1/jobs/01HFAKE0000000000000000000/cancel", headers=auth_headers)
    assert r.status_code == 404