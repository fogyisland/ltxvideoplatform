# app/api/uploads.py
from __future__ import annotations
import ulid
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.db.session import get_db
from app.db.models import Upload, User
from app.storage import files

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])

ALLOWED = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


def save_bytes_record(user_id: int, data: bytes, ext: str, db: Session) -> Upload:
    """Programmatic upload helper (used by scene chaining from previous frame).

    Persists the file + DB row, returns the Upload ORM object.
    """
    path, sha = files.save_upload(user_id, data, ext)
    rec = Upload(
        id=str(ulid.ULID()),
        user_id=user_id,
        path=str(path.relative_to(files.uploads_dir)),
        kind="image",
        sha256=sha,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.post("")
async def upload_image(
    file: UploadFile = File(...), u: User = Depends(current_user), db: Session = Depends(get_db)
):
    if file.content_type not in ALLOWED:
        raise HTTPException(415, f"unsupported type: {file.content_type}")
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "file too large (>20MB)")
    rec = save_bytes_record(u.id, data, ALLOWED[file.content_type], db)
    return {"id": rec.id, "path": rec.path, "sha256": rec.sha256}


@router.post("")
async def upload_image(
    file: UploadFile = File(...), u: User = Depends(current_user), db: Session = Depends(get_db)
):
    if file.content_type not in ALLOWED:
        raise HTTPException(415, f"unsupported type: {file.content_type}")
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "file too large (>20MB)")
    path, sha = files.save_upload(u.id, data, ALLOWED[file.content_type])
    rec = Upload(id=str(ulid.ULID()), user_id=u.id, path=str(path.relative_to(files.uploads_dir)), kind="image", sha256=sha)
    db.add(rec); db.commit(); db.refresh(rec)
    return {"id": rec.id, "path": rec.path, "sha256": rec.sha256}
