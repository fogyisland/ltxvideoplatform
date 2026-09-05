"""app/core/job_runner.py

Drives a single job from `queued` to a terminal state.

The inference call goes through ``app.core.ltx_wrappers.get_pipeline`` (which
caches the loaded pipeline per process) and then ``ltx_generate``. The runner
itself is async; all blocking work runs in ``asyncio.to_thread`` so the event
loop is never starved; everything is wrapped in ``asyncio.wait_for`` so the
``JOB_TIMEOUT_SEC`` ceiling is enforced.
"""
from __future__ import annotations

import asyncio
import io
import json
import time
from datetime import datetime, timezone

import ulid
from PIL import Image
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import pipeline_manager as pm_mod
from app.core import registry as reg_mod
from app.core.ltx_wrappers import generate as ltx_generate
from app.core.ltx_wrappers import get_pipeline, unload_pipeline
from app.db.models import Job, JobStage, JobStatus, Upload
from app.storage import files


async def run(job_id: str, db: Session) -> None:
    """Execute a job end-to-end. Errors are caught and persisted on the row."""
    s = get_settings()
    j: Job | None = db.get(Job, job_id)
    if j is None:
        return
    if j.status == JobStatus.cancelled:
        return

    # Apply per-job mode override: "auto" honors VRAM (handled by ltx_wrappers),
    # "cpu" forces the CPU path, "gpu" forces the official GPU path (requires
    # >=16GB VRAM). The env var only takes effect for the duration of this job.
    params_preview = json.loads(j.params_json)
    _mode = (params_preview.get("_mode") or "auto").lower()
    if _mode == "gpu":
        os.environ["LTX_FORCE_GPU"] = "1"
    elif _mode == "cpu":
        os.environ["LTX_FORCE_GPU"] = "0"
    # "auto" leaves the env var as set at process start.

    # ---- model_load branch (early return) ----
    if j.kind == "model_load":
        params = json.loads(j.params_json)
        if params.get("op") == "unload":
            unload_pipeline(j.model_id)
            pm_mod.get_manager().unload()
        else:
            # Warm the cache + touch the singleton so /models/current reflects it
            get_pipeline(j.model_id)
            pm_mod.get_manager().load(j.model_id, loader=lambda _: get_pipeline(j.model_id))
        j.status = JobStatus.succeeded
        j.finished_at = datetime.now(timezone.utc)
        db.commit()
        return

    # ---- Mark as running ----
    j.status = JobStatus.running
    j.stage = JobStage.loading_model
    j.started_at = datetime.now(timezone.utc)
    db.commit()

    try:
        # ---- Pipeline load (lazy, cached per process) ----
        await asyncio.wait_for(
            asyncio.to_thread(_ensure_pipeline, j.model_id),
            timeout=s.job_timeout_sec,
        )

        params = json.loads(j.params_json)
        j.stage = JobStage.encoding
        db.commit()

        # ---- extend branch: convert to i2v by extracting parent's last frame ----
        if j.kind == "extend":
            if not j.parent_job_id:
                raise RuntimeError("extend job has no parent_job_id")
            parent = db.get(Job, j.parent_job_id)
            if parent is None or not parent.output_path:
                raise RuntimeError(f"parent job missing or has no output: {j.parent_job_id}")
            parent_video = s.data_dir_abs / parent.output_path
            if not parent_video.exists():
                raise FileNotFoundError(f"parent video missing: {parent_video}")
            image = _extract_last_frame(parent_video)
            # upload the PNG so it can be referenced by id (kept for audit)
            png_bytes = _png_bytes(image)
            upload_path, sha = files.save_upload(j.user_id, png_bytes, ".png")
            up_rec = Upload(
                id=str(ulid.ULID()), user_id=j.user_id,
                path=str(upload_path.relative_to(files.uploads_dir())),
                kind="image", sha256=sha,
            )
            db.add(up_rec); db.commit()
            params["image_upload_id"] = up_rec.id
            params.setdefault("strength", 0.6)
            j.params_json = json.dumps(params)
            j.kind = "i2v"
            db.commit()

        progress_state = {"p": 0.0}

        def _on_step(step: int, total: int) -> None:
            j.stage = JobStage.denoising
            j.progress = step / total if total else 0.0
            if step % 5 == 0 or step == total:
                db.commit()

        def _run_inference() -> bytes:
            j.stage = JobStage.denoising
            db.commit()
            image = _resolve_image(j, db)
            call_params = dict(params)
            call_params.pop("image_upload_id", None)
            mp4 = ltx_generate(
                pipeline=get_pipeline(j.model_id),
                kind=j.kind,
                on_step=_on_step,
                image=image,
                **call_params,
            )
            j.stage = JobStage.decoding
            j.progress = 1.0
            db.commit()
            return mp4

        t0 = time.time()
        mp4_bytes = await asyncio.wait_for(
            asyncio.to_thread(_run_inference),
            timeout=s.job_timeout_sec,
        )

        j.stage = JobStage.writing
        db.commit()

        out_path = files.save_output(j.user_id, j.id, mp4_bytes)
        j.output_path = str(out_path.relative_to(s.data_dir_abs))
        j.duration_sec = time.time() - t0
        j.status = JobStatus.succeeded
        j.finished_at = datetime.now(timezone.utc)
        db.commit()
        # Aggressive VRAM reclamation between jobs (8 GB cards run right
        # at the edge; tiny leftover tensors can OOM the next request).
        import gc as _gc
        _gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception as e:
        j.status = JobStatus.failed
        j.error = repr(e)[:2000]
        j.finished_at = datetime.now(timezone.utc)
        db.commit()
        # Free VRAM even on failure so we don't accumulate leaked tensors
        import gc as _gc
        try:
            _gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
        except Exception:
            pass


# ---------- helpers ----------

def _ensure_pipeline(model_id: str) -> None:
    """Build the pipeline if not already cached. Lazy + memoized."""
    get_pipeline(model_id)


def _resolve_image(job: Job, db: Session) -> Image.Image | None:
    """Resolve the optional image_upload_id param to a PIL.Image."""
    try:
        params = json.loads(job.params_json)
    except Exception:
        params = {}
    upload_id = params.get("image_upload_id")
    if not upload_id:
        return None
    up = db.get(Upload, upload_id)
    if up is None:
        return None
    full_path = files.uploads_dir() / up.path
    if not full_path.exists():
        return None
    return Image.open(full_path)


def _extract_last_frame(mp4_path) -> Image.Image:
    import imageio.v2 as imageio
    reader = imageio.get_reader(str(mp4_path))
    try:
        meta = reader.get_meta_data()
        nframes = int(meta.get("nframes", 0)) if isinstance(meta, dict) else 0
        if nframes <= 0:
            nframes = reader.count_frames()
    finally:
        reader.close()
    last_idx = max(0, int(nframes) - 1)
    reader = imageio.get_reader(str(mp4_path))
    try:
        frame_arr = reader.get_data(last_idx)
    finally:
        reader.close()
    return Image.fromarray(frame_arr)


def _png_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()
