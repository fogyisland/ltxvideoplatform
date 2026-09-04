# app/api/jobs.py
from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.core import job_queue as jq
from app.config import get_settings
from app.db.session import get_db
from app.db.models import Job, User
from app.storage import files

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _serialize(j: Job) -> dict:
    return {
        "id": j.id, "user_id": j.user_id, "kind": j.kind, "model_id": j.model_id,
        "params": json.loads(j.params_json),
        "status": j.status.value, "progress": j.progress, "stage": j.stage.value,
        "error": j.error, "output_path": j.output_path, "preview_path": j.preview_path,
        "parent_job_id": j.parent_job_id, "duration_sec": j.duration_sec,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "finished_at": j.finished_at.isoformat() if j.finished_at else None,
    }


@router.get("/{job_id}")
def get_job(job_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if j is None or j.user_id != u.id:
        raise HTTPException(404, "job not found")
    return _serialize(j)


@router.get("/{job_id}/result")
def get_result(job_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if j is None or j.user_id != u.id:
        raise HTTPException(404, "job not found")
    if not j.output_path:
        raise HTTPException(409, "job has no output yet")
    s = get_settings()
    p = s.data_dir_abs / j.output_path
    if not files.verify_owner(p, u.id):
        raise HTTPException(403, "forbidden")
    return FileResponse(p, media_type="video/mp4", filename=f"{job_id}.mp4")


@router.post("/{job_id}/cancel")
def cancel(job_id: str, u: User = Depends(current_user)):
    j = jq.get_queue().status(job_id)
    if j is None or j.user_id != u.id:
        raise HTTPException(404, "job not found")
    return {"ok": jq.get_queue().cancel(job_id)}


@router.get("/{job_id}/preview")
def get_preview(job_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if j is None or j.user_id != u.id:
        raise HTTPException(404, "job not found")
    if not j.preview_path:
        raise HTTPException(404, "no preview yet")
    s = get_settings()
    p = s.data_dir_abs / j.preview_path
    return FileResponse(p, media_type="image/png")
