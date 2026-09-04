# app/api/admin.py
"""Admin-only endpoints. All routes require admin role."""
from __future__ import annotations
import os
import re
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.auth.deps import require_admin
from app.auth.passwords import hash_password
from app.config import get_settings
from app.core import registry as reg_mod
from app.core import pipeline_manager as pm_mod
from app.core.job_queue import get_queue
from app.db.session import get_db
from app.db.models import User, Role, Job, JobStatus, Model

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ---------- users ----------

class AdminUserOut(BaseModel):
    id: int
    username: str
    email: str | None
    role: str
    is_active: bool
    created_at: str
    last_login_at: str | None


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: EmailStr | None = None
    password: str = Field(min_length=8, max_length=128)
    role: Literal["user", "admin"] = "user"


class AdminUserPatch(BaseModel):
    is_active: bool | None = None
    role: Literal["user", "admin"] | None = None


class AdminResetPassword(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


@router.get("/users", response_model=list[AdminUserOut])
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(User).order_by(User.created_at.desc()).all()
    return [_u(u) for u in rows]


@router.post("/users", response_model=AdminUserOut, status_code=201)
def create_user(body: AdminUserCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not re.match(r"^[A-Za-z0-9_.-]{3,32}$", body.username):
        raise HTTPException(400, "username must be 3-32 chars, letters/digits/._- only")
    if db.query(User).filter_by(username=body.username).first():
        raise HTTPException(409, "username already taken")
    if body.email and db.query(User).filter_by(email=body.email).first():
        raise HTTPException(409, "email already registered")
    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
        role=Role(body.role),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _u(user)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def patch_user(user_id: int, body: AdminUserPatch, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    if body.is_active is not None:
        # prevent admin from disabling themselves
        if body.is_active is False and user.id == admin.id:
            raise HTTPException(400, "cannot disable yourself")
        user.is_active = body.is_active
    if body.role is not None:
        # prevent admin from demoting themselves
        if body.role != "admin" and user.id == admin.id:
            raise HTTPException(400, "cannot demote yourself")
        user.role = Role(body.role)
    db.commit()
    db.refresh(user)
    return _u(user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if user_id == admin.id:
        raise HTTPException(400, "cannot delete yourself")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    user.is_active = False
    db.commit()
    return None


@router.post("/users/{user_id}/reset-password", status_code=204)
def reset_password(user_id: int, body: AdminResetPassword, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return None


# ---------- models (registry + download status) ----------

_DOWNLOAD_STATUS: dict[str, dict] = {}  # in-memory: model_id -> {status, progress, message}
_DOWNLOAD_LOCKS: dict[str, threading.Lock] = {}


@router.get("/models")
def list_models_admin(_: User = Depends(require_admin)):
    reg = reg_mod.load(get_settings().registry_path)
    out = []
    for entry in reg.models:
        ckpt = get_settings().model_dir_abs / entry.checkpoint_path
        cfg = get_settings().model_dir_abs / entry.config_path
        present = ckpt.exists() and cfg.exists()
        size_gb = round(ckpt.stat().st_size / (1024 ** 3), 2) if ckpt.exists() else 0.0
        st = _DOWNLOAD_STATUS.get(entry.id, {"status": "idle", "progress": 0.0, "message": ""})
        out.append({
            "id": entry.id,
            "display_name": entry.display_name,
            "kind": entry.kind,
            "vram_gb": entry.vram_gb,
            "default_steps": entry.default_steps,
            "default_frames": entry.default_frames,
            "enabled": entry.enabled,
            "description": entry.description,
            "checkpoint_path": entry.checkpoint_path,
            "config_path": entry.config_path,
            "downloaded": present,
            "size_gb": size_gb,
            "download_status": st,
        })
    return out


@router.post("/models/{model_id}/download", status_code=202)
def trigger_download(model_id: str, _: User = Depends(require_admin)):
    reg = reg_mod.load(get_settings().registry_path)
    entry = reg.by_id(model_id)
    if entry is None:
        raise HTTPException(404, "model not found")
    if _DOWNLOAD_STATUS.get(model_id, {}).get("status") == "running":
        raise HTTPException(409, "download already in progress")

    lock = _DOWNLOAD_LOCKS.setdefault(model_id, threading.Lock())
    _DOWNLOAD_STATUS[model_id] = {"status": "running", "progress": 0.0, "message": "starting"}

    def _run():
        try:
            from huggingface_hub import snapshot_download
            settings = get_settings()
            target_dir = settings.model_dir_abs / Path(entry.checkpoint_path).parent
            target_dir.mkdir(parents=True, exist_ok=True)
            _DOWNLOAD_STATUS[model_id] = {"status": "running", "progress": 0.05,
                                          "message": f"downloading into {target_dir.name}"}
            snapshot_download(
                repo_id="Lightricks/LTX-Video",
                local_dir=str(settings.model_dir_abs),
                token=settings.hf_token or None,
                allow_patterns=[
                    f"{Path(entry.checkpoint_path).parent}/**",
                    f"{Path(entry.config_path).parent}/**",
                ],
            )
            _DOWNLOAD_STATUS[model_id] = {"status": "done", "progress": 1.0, "message": "complete"}
        except Exception as e:
            _DOWNLOAD_STATUS[model_id] = {"status": "failed", "progress": 0.0,
                                          "message": f"{type(e).__name__}: {e}"}

    t = threading.Thread(target=_run, daemon=True, name=f"dl-{model_id}")
    t.start()
    return {"model_id": model_id, "status": "started"}


@router.get("/models/{model_id}/download/status")
def download_status(model_id: str, _: User = Depends(require_admin)):
    return _DOWNLOAD_STATUS.get(model_id, {"status": "idle", "progress": 0.0, "message": ""})


# ---------- stats ----------

@router.get("/stats")
def stats(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    settings = get_settings()
    # GPU/VRAM
    gpu = {"name": None, "vram_used_gb": 0.0, "vram_total_gb": 0.0, "available": False}
    try:
        import torch
        if torch.cuda.is_available():
            free, total = torch.cuda.mem_get_info()
            gpu["name"] = torch.cuda.get_device_name(0)
            gpu["vram_used_gb"] = round((total - free) / (1024 ** 3), 2)
            gpu["vram_total_gb"] = round(total / (1024 ** 3), 2)
            gpu["available"] = True
    except Exception:
        pass

    # Disk
    data_disk = shutil.disk_usage(settings.data_dir_abs)
    model_disk = shutil.disk_usage(settings.model_dir_abs) if settings.model_dir_abs.exists() else data_disk
    disk = {
        "data_free_gb": round(data_disk.free / (1024 ** 3), 2),
        "data_total_gb": round(data_disk.total / (1024 ** 3), 2),
        "model_free_gb": round(model_disk.free / (1024 ** 3), 2),
        "model_total_gb": round(model_disk.total / (1024 ** 3), 2),
    }

    # Counts
    user_count = db.query(User).count()
    active_user_count = db.query(User).filter_by(is_active=True).count()
    job_counts = {
        "queued": db.query(Job).filter_by(status=JobStatus.queued).count(),
        "running": db.query(Job).filter_by(status=JobStatus.running).count(),
        "succeeded": db.query(Job).filter_by(status=JobStatus.succeeded).count(),
        "failed": db.query(Job).filter_by(status=JobStatus.failed).count(),
    }
    # Pipeline
    pm = pm_mod.get_manager()
    pipe = pm.current_id or "none"

    # Recent jobs (last 20)
    recent = db.query(Job).order_by(Job.created_at.desc()).limit(20).all()
    recent_out = [{
        "id": j.id,
        "username": (db.get(User, j.user_id).username if db.get(User, j.user_id) else "?"),
        "kind": j.kind,
        "model_id": j.model_id,
        "status": j.status.value,
        "created_at": j.created_at.isoformat() if j.created_at else None,
    } for j in recent]

    return {
        "gpu": gpu,
        "disk": disk,
        "users": {"total": user_count, "active": active_user_count},
        "jobs": job_counts,
        "pipeline": {"current_id": pipe},
        "recent_jobs": recent_out,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


# ---------- helpers ----------

def _u(u: User) -> AdminUserOut:
    return AdminUserOut(
        id=u.id,
        username=u.username,
        email=u.email,
        role=u.role.value,
        is_active=u.is_active,
        created_at=u.created_at.isoformat() if u.created_at else "",
        last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
    )