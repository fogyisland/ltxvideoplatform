# app/api/projects.py
"""Project + Scene CRUD for the long-form "video studio" workflow."""
from __future__ import annotations
import json
import os
import ulid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.config import get_settings
from app.core.job_queue import get_queue
from app.db.session import get_db
from app.db.models import User, Project, ProjectStatus, Scene, SceneStatus, Job, JobStatus, Upload
from app.api.uploads import save_bytes_record

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


# ---------- schemas ----------

class SceneOut(BaseModel):
    id: str
    project_id: str
    position: int
    prompt: str
    image_upload_id: str | None
    duration: str
    quality: str
    status: str
    job_id: str | None
    output_path: str | None
    error: str | None
    created_at: str


class ProjectOut(BaseModel):
    id: str
    title: str
    style: str
    model_id: str
    status: str
    created_at: str
    updated_at: str
    scenes: list[SceneOut] = []


class ProjectSummary(BaseModel):
    id: str
    title: str
    style: str
    status: str
    scene_count: int
    succeeded_count: int
    updated_at: str


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    style: str = "Cinematic"
    model_id: str = "ltx-13b-distilled-long-multi-shot"


class ProjectPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    style: str | None = None
    model_id: str | None = None
    status: str | None = None


class SceneCreate(BaseModel):
    prompt: str = Field(default="", max_length=2000)
    image_upload_id: str | None = None
    duration: str = "medium"
    quality: str = "standard"
    position: int | None = None  # null = append


class ScenePatch(BaseModel):
    prompt: str | None = Field(default=None, max_length=2000)
    image_upload_id: str | None = None
    duration: str | None = None
    quality: str | None = None
    position: int | None = None


class ReorderIn(BaseModel):
    scene_ids: list[str]  # new order


# ---------- helpers ----------

def _scene(s: Scene) -> SceneOut:
    return SceneOut(
        id=s.id, project_id=s.project_id, position=s.position, prompt=s.prompt,
        image_upload_id=s.image_upload_id, duration=s.duration, quality=s.quality,
        status=s.status.value if hasattr(s.status, "value") else str(s.status),
        job_id=s.job_id, output_path=s.output_path, error=s.error,
        created_at=s.created_at.isoformat() if s.created_at else "",
    )


def _project(p: Project, with_scenes: bool = True) -> ProjectOut:
    return ProjectOut(
        id=p.id, title=p.title, style=p.style, model_id=p.model_id,
        status=p.status.value if hasattr(p.status, "value") else str(p.status),
        created_at=p.created_at.isoformat() if p.created_at else "",
        updated_at=p.updated_at.isoformat() if p.updated_at else "",
        scenes=[_scene(s) for s in sorted(p.scenes, key=lambda x: x.position)] if with_scenes else [],
    )


def _owns(project_id: str, user: User, db: Session) -> Project:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "project not found")
    if p.user_id != user.id:
        raise HTTPException(403, "forbidden")
    return p


# ---------- project CRUD ----------

@router.get("", response_model=list[ProjectSummary])
def list_projects(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Project).filter_by(user_id=user.id).order_by(Project.updated_at.desc()).all()
    out = []
    for p in rows:
        scenes = p.scenes
        out.append(ProjectSummary(
            id=p.id, title=p.title, style=p.style,
            status=p.status.value if hasattr(p.status, "value") else str(p.status),
            scene_count=len(scenes),
            succeeded_count=sum(1 for s in scenes if s.status == SceneStatus.succeeded),
            updated_at=p.updated_at.isoformat() if p.updated_at else "",
        ))
    return out


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    pid = str(ulid.ULID())
    p = Project(
        id=pid,
        user_id=user.id,
        title=body.title,
        style=body.style,
        model_id=body.model_id,
        status=ProjectStatus.draft,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    # start with one empty scene so the editor has something to focus
    sid = str(ulid.ULID())
    s = Scene(id=sid, project_id=pid, position=0, prompt="", status=SceneStatus.draft)
    db.add(s)
    db.commit()
    db.refresh(p)
    return _project(p)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _owns(project_id, user, db)
    return _project(p)


@router.patch("/{project_id}", response_model=ProjectOut)
def patch_project(project_id: str, body: ProjectPatch,
                  user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _owns(project_id, user, db)
    if body.title is not None:
        p.title = body.title
    if body.style is not None:
        p.style = body.style
    if body.model_id is not None:
        p.model_id = body.model_id
    if body.status is not None:
        try:
            p.status = ProjectStatus(body.status)
        except ValueError:
            raise HTTPException(400, "invalid status")
    db.commit()
    db.refresh(p)
    return _project(p)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _owns(project_id, user, db)
    # delete output files
    s = get_settings()
    for scene in p.scenes:
        if scene.output_path:
            try:
                (s.data_dir_abs / scene.output_path).unlink(missing_ok=True)
            except Exception:
                pass
    db.delete(p)
    db.commit()


# ---------- scene CRUD ----------

@router.post("/{project_id}/scenes", response_model=SceneOut, status_code=201)
def add_scene(project_id: str, body: SceneCreate,
              user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _owns(project_id, user, db)
    # determine position
    if body.position is not None:
        # shift everything at/after this position
        existing = [s for s in p.scenes if s.position >= body.position]
        for s in existing:
            s.position += 1
        pos = body.position
    else:
        pos = max((s.position for s in p.scenes), default=-1) + 1
    sid = str(ulid.ULID())
    s = Scene(
        id=sid, project_id=p.id, position=pos, prompt=body.prompt,
        image_upload_id=body.image_upload_id, duration=body.duration,
        quality=body.quality, status=SceneStatus.draft,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    p.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _scene(s)


@router.patch("/{project_id}/scenes/{scene_id}", response_model=SceneOut)
def patch_scene(project_id: str, scene_id: str, body: ScenePatch,
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _owns(project_id, user, db)
    s = db.get(Scene, scene_id)
    if s is None or s.project_id != p.id:
        raise HTTPException(404, "scene not found")
    if body.prompt is not None:
        s.prompt = body.prompt
    if body.image_upload_id is not None:
        s.image_upload_id = body.image_upload_id
    if body.duration is not None:
        s.duration = body.duration
    if body.quality is not None:
        s.quality = body.quality
    if body.position is not None and body.position != s.position:
        # simple reorder: place at new position, shift others
        old = s.position
        new = body.position
        if new > old:
            for other in p.scenes:
                if other.id != s.id and old < other.position <= new:
                    other.position -= 1
        else:
            for other in p.scenes:
                if other.id != s.id and new <= other.position < old:
                    other.position += 1
        s.position = new
    db.commit()
    db.refresh(s)
    p.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _scene(s)


@router.delete("/{project_id}/scenes/{scene_id}", status_code=204)
def delete_scene(project_id: str, scene_id: str,
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _owns(project_id, user, db)
    s = db.get(Scene, scene_id)
    if s is None or s.project_id != p.id:
        raise HTTPException(404, "scene not found")
    # remove output file
    if s.output_path:
        try:
            (get_settings().data_dir_abs / s.output_path).unlink(missing_ok=True)
        except Exception:
            pass
    deleted_pos = s.position
    db.delete(s)
    db.commit()
    # shift others down
    for other in p.scenes:
        if other.position > deleted_pos:
            other.position -= 1
    db.commit()
    p.updated_at = datetime.now(timezone.utc)
    db.commit()


@router.post("/{project_id}/scenes/reorder", response_model=ProjectOut)
def reorder_scenes(project_id: str, body: ReorderIn,
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _owns(project_id, user, db)
    by_id = {s.id: s for s in p.scenes}
    for i, sid in enumerate(body.scene_ids):
        if sid in by_id:
            by_id[sid].position = i
    db.commit()
    db.refresh(p)
    return _project(p)


# ---------- per-scene generation ----------

@router.post("/{project_id}/scenes/{scene_id}/generate", response_model=SceneOut, status_code=202)
def generate_scene(project_id: str, scene_id: str,
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Submit a single scene as a generation job.

    For chaining (last-frame → first-frame), the previous scene's
    job's output_path is uploaded automatically and used as image_upload_id.
    """
    p = _owns(project_id, user, db)
    s = db.get(Scene, scene_id)
    if s is None or s.project_id != p.id:
        raise HTTPException(404, "scene not found")
    if not s.prompt.strip() and not s.image_upload_id:
        raise HTTPException(400, "scene needs a prompt or an image")

    q = get_queue()

    # chain: if this scene has no image, use the previous successful scene's last frame
    chain_upload_id = s.image_upload_id
    if not chain_upload_id:
        prev = sorted([x for x in p.scenes if x.position < s.position],
                      key=lambda x: x.position, reverse=True)
        for prev_scene in prev:
            if prev_scene.status == SceneStatus.succeeded and prev_scene.output_path:
                # extract last frame and upload as image
                try:
                    settings = get_settings()
                    last_frame_bytes = _extract_last_frame_bytes(
                        settings.data_dir_abs / prev_scene.output_path
                    )
                    up = save_bytes_record(user.id, last_frame_bytes, ".png", db)
                    chain_upload_id = up.id
                except Exception:
                    pass  # continue without chain
                break

    # build params
    duration_map = {"short": 97, "medium": 161, "long": 241}
    quality_steps = {"draft": 8, "standard": 20, "high": 40}
    num_frames = duration_map.get(s.duration, 161)
    steps = quality_steps.get(s.quality, 20)

    # enqueue via job_queue
    if chain_upload_id:
        params = {
            "prompt": s.prompt, "image_upload_id": chain_upload_id,
            "strength": 0.6, "num_frames": num_frames, "height": 480, "width": 768,
            "num_inference_steps": steps, "guidance_scale": 5.0, "fps": 24,
        }
        job_id = q.submit(kind="i2v", user_id=user.id, model_id=p.model_id, params=params)
    else:
        params = {
            "prompt": s.prompt, "num_frames": num_frames, "height": 480, "width": 768,
            "num_inference_steps": steps, "guidance_scale": 5.0, "fps": 24,
        }
        job_id = q.submit(kind="t2v", user_id=user.id, model_id=p.model_id, params=params)

    s.job_id = job_id
    s.status = SceneStatus.queued
    s.error = None
    db.commit()
    db.refresh(s)
    p.status = ProjectStatus.rendering
    p.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _scene(s)


def _extract_last_frame_bytes(mp4_path: Path) -> bytes:
    """Extract the last frame of an MP4 and return PNG bytes."""
    import imageio.v2 as imageio
    from PIL import Image
    import io
    reader = imageio.get_reader(str(mp4_path))
    last = None
    for frame in reader:
        last = frame
    reader.close()
    if last is None:
        raise ValueError("no frames in mp4")
    img = Image.fromarray(last)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()