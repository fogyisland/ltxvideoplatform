# app/api/history.py
from __future__ import annotations
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.config import get_settings
from app.db.session import get_db
from app.db.models import Job, User
from app.storage import files

router = APIRouter(prefix="/api/v1/history", tags=["history"])


@router.get("")
def list_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    kind: str | None = None,
    u: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Job).filter(Job.user_id == u.id)
    if kind:
        q = q.filter(Job.kind == kind)
    q = q.order_by(Job.created_at.desc()).limit(limit).offset(offset)
    return [{
        "id": j.id, "kind": j.kind, "model_id": j.model_id, "status": j.status.value,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "output_path": j.output_path,
    } for j in q]


@router.get("/{job_id}")
def get_history_item(job_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if j is None or j.user_id != u.id:
        raise HTTPException(404, "not found")
    return {
        "id": j.id, "kind": j.kind, "model_id": j.model_id, "params": json.loads(j.params_json),
        "status": j.status.value, "progress": j.progress, "stage": j.stage.value,
        "output_path": j.output_path, "error": j.error,
        "created_at": j.created_at.isoformat() if j.created_at else None,
    }


@router.delete("/{job_id}")
def delete_history_item(job_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if j is None or j.user_id != u.id:
        raise HTTPException(404, "not found")
    if j.output_path:
        s = get_settings()
        p = s.data_dir_abs / j.output_path
        if files.verify_owner(p, u.id) and p.exists():
            p.unlink()
    db.delete(j); db.commit()
    return {"ok": True}
