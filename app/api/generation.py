# app/api/generation.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import GenerateIn
from app.auth.deps import current_user
from app.core import job_queue as jq
from app.core import registry as reg_mod
from app.config import get_settings
from app.db.session import get_db
from app.db.models import User

router = APIRouter(prefix="/api/v1", tags=["generation"])


def _enqueue(u: User, kind: str, params: dict) -> str:
    reg = reg_mod.load(get_settings().registry_path)
    entry = reg.by_id(params["model_id"])
    if entry is None or not entry.enabled:
        raise HTTPException(400, f"model not available: {params['model_id']}")
    return jq.get_queue().submit(kind=kind, user_id=u.id, model_id=params["model_id"], params=params)


@router.post("/t2v", status_code=202)
def t2v(req: GenerateIn, u: User = Depends(current_user)):
    return {"job_id": _enqueue(u, "t2v", req.model_dump())}


@router.post("/i2v", status_code=202)
def i2v(req: GenerateIn, u: User = Depends(current_user)):
    if not req.image_upload_id:
        raise HTTPException(400, "image_upload_id required")
    return {"job_id": _enqueue(u, "i2v", req.model_dump())}


@router.post("/keyframe", status_code=202)
def keyframe(req: GenerateIn, u: User = Depends(current_user)):
    if not req.frame_uploads:
        raise HTTPException(400, "frame_uploads required")
    return {"job_id": _enqueue(u, "keyframe", req.model_dump())}


@router.post("/extend", status_code=202)
def extend(req: GenerateIn, u: User = Depends(current_user)):
    if not req.parent_job_id:
        raise HTTPException(400, "parent_job_id required")
    return {"job_id": _enqueue(u, "extend", req.model_dump(exclude={"parent_job_id"}), parent_job_id=req.parent_job_id)}


@router.post("/upscale", status_code=202)
def upscale(req: GenerateIn, u: User = Depends(current_user)):
    if not req.parent_job_id:
        raise HTTPException(400, "parent_job_id required")
    return {"job_id": _enqueue(u, "upscale", req.model_dump(exclude={"parent_job_id"}), parent_job_id=req.parent_job_id)}
