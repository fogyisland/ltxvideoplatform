# app/api/files.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.auth.deps import current_user
from app.config import get_settings
from app.db.models import User
from app.storage import files

router = APIRouter(prefix="/api/v1/files", tags=["files"])


@router.get("/{path:path}")
def get_file(path: str, u: User = Depends(current_user)):
    s = get_settings()
    p = (s.data_dir_abs / path).resolve()
    try:
        p.relative_to(s.data_dir_abs)  # ensure inside data dir
    except ValueError:
        raise HTTPException(400, "bad path")
    if not files.verify_owner(p, u.id):
        raise HTTPException(403, "forbidden")
    if not p.exists():
        raise HTTPException(404, "not found")
    return FileResponse(p)
