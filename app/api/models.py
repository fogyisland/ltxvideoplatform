# app/api/models.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import ModelOut
from app.auth.deps import current_user
from app.config import get_settings
from app.core import pipeline_manager as pm_mod
from app.core import registry as reg_mod
from app.core import job_queue as jq
from app.db.session import get_db
from app.db.models import User

router = APIRouter(prefix="/api/v1/models", tags=["models"])


@router.get("", response_model=list[ModelOut])
def list_models(_: User = Depends(current_user)):
    reg = reg_mod.load(get_settings().registry_path)
    return [ModelOut(
        id=e.id, display_name=e.display_name, kind=e.kind,
        default_steps=e.default_steps, default_frames=e.default_frames,
        vram_gb=e.vram_gb, enabled=e.enabled, description=e.description,
    ) for e in reg.models]


@router.get("/current")
def current(_: User = Depends(current_user)):
    return pm_mod.get_manager().status()


@router.post("/{model_id}/load", status_code=202)
def load_model(model_id: str, u: User = Depends(current_user)):
    job_id = jq.get_queue().submit(
        kind="model_load", user_id=u.id, model_id=model_id, params={"op": "load"}
    )
    return {"job_id": job_id}


@router.post("/unload", status_code=202)
def unload_model(u: User = Depends(current_user)):
    job_id = jq.get_queue().submit(
        kind="model_load", user_id=u.id, model_id="__unload__", params={"op": "unload"}
    )
    return {"job_id": job_id}
