# app/storage/files.py
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from app.config import get_settings

_settings = get_settings()

# Module-level base directories. Tests monkeypatch these directly
# (e.g. monkeypatch.setattr(files, "uploads_dir", tmp_path / "uploads")).
uploads_dir: Path = _settings.uploads_dir
outputs_dir: Path = _settings.outputs_dir
previews_dir: Path = _settings.previews_dir


def resolve(user_id: int, kind: Literal["uploads", "outputs", "previews"], name: str) -> Path:
    base = {"uploads": uploads_dir, "outputs": outputs_dir, "previews": previews_dir}[kind]
    user_root = (base / str(user_id)).resolve()
    p = (base / str(user_id) / name).resolve()
    # Defensive: ensure resolved path is still inside the user's directory
    if not str(p).startswith(str(user_root)):
        raise ValueError("path escapes user directory")
    return p


def verify_owner(path: Path, user_id: int) -> bool:
    path = Path(path).resolve()
    parts = path.parts
    try:
        i = parts.index("uploads") if "uploads" in parts else parts.index("outputs")
    except ValueError:
        return False
    return i + 1 < len(parts) and parts[i + 1] == str(user_id)


def save_upload(user_id: int, data: bytes, ext: str) -> tuple[Path, str]:
    sha = hashlib.sha256(data).hexdigest()
    name = f"{sha}{ext}"
    p = resolve(user_id, "uploads", name)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_bytes(data)
    return p, sha


def save_output(user_id: int, job_id: str, video_bytes: bytes, ext: str = ".mp4") -> Path:
    name = f"{job_id}{ext}"
    p = resolve(user_id, "outputs", name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(video_bytes)
    return p
