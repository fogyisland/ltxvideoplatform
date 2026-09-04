"""Job runner: drives a single job from ``queued`` to a terminal state.

The runner is an ``async`` coroutine that is always called inside the
:class:`JobQueue` worker. All blocking work (model load, inference, file
I/O) is dispatched via :func:`asyncio.to_thread` so the event loop is never
starved. The whole pipeline is wrapped in :func:`asyncio.wait_for` so that
``JOB_TIMEOUT_SEC`` is enforced end-to-end.

DB writes happen on the session passed in by the worker. The runner mutates
``Job.status``, ``Job.stage``, ``Job.progress``, ``Job.error``,
``Job.output_path``, ``Job.started_at``, ``Job.finished_at``, and
``Job.duration_sec`` directly.
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
from app.db.models import Job, JobStage, JobStatus, Upload
from app.storage import files


async def run(job_id: str, db: Session) -> None:
    """Execute a job end-to-end and persist progress to ``db``.

    Errors are caught and recorded on the job row; this function never
    re-raises (the worker is responsible for crash reporting).
    """
    s = get_settings()
    j: Job | None = db.get(Job, job_id)
    if j is None:
        return
    if j.status == JobStatus.cancelled:
        return

    # ---- model_load branch (early return: no inference) ----
    # Placed at the top so ``POST /api/v1/models/{id}/load`` does not try
    # to allocate an inference pipeline. ``op=unload`` is also handled here
    # (model_id is the sentinel "__unload__" set by app.api.models).
    if j.kind == "model_load":
        params = json.loads(j.params_json)
        if params.get("op") == "unload":
            pm_mod.get_manager().unload()
        else:
            pm_mod.get_manager().load(j.model_id, loader=_real_loader_for(j.model_id))
        j.status = JobStatus.succeeded
        j.finished_at = datetime.now(timezone.utc)
        db.commit()
        return

    # ---- Mark as running ----
    j.status = JobStatus.running
    j.stage = JobStage.loading_model
    j.started_at = datetime.now(timezone.utc)
    db.commit()

    pm = pm_mod.get_manager()

    def _ensure_loaded(model_id: str) -> None:
        # If the requested model is already loaded, skip.
        if pm.current_id == model_id:
            return
        reg = reg_mod.load(s.registry_path)
        entry = reg.by_id(model_id)
        if entry is None:
            raise RuntimeError(f"unknown model: {model_id}")
        ckpt = s.model_dir_abs / entry.checkpoint_path
        if not ckpt.exists():
            raise FileNotFoundError(f"checkpoint missing: {ckpt}")
        # Real loader wiring (uses LTXVideoPipeline.from_pretrained).
        pm.load(model_id, loader=_real_loader_for(model_id))

    try:
        await asyncio.wait_for(
            asyncio.to_thread(_ensure_loaded, j.model_id),
            timeout=s.job_timeout_sec,
        )

        params = json.loads(j.params_json)
        j.stage = JobStage.encoding
        db.commit()

        # ---- extend branch: extract last frame from parent output, save as upload ----
        # Convert the ``extend`` job into an ``i2v`` job by:
        #   1. Reading the parent's output MP4.
        #   2. Grabbing the last frame via imageio.
        #   3. Persisting it as an Upload row (PNG).
        #   4. Setting image_upload_id + default strength on the params.
        # From here, the inference path is identical to a normal i2v job.
        if j.kind == "extend":
            if not j.parent_job_id:
                raise RuntimeError("extend job has no parent_job_id")
            parent = db.get(Job, j.parent_job_id)
            if parent is None or not parent.output_path:
                raise RuntimeError(
                    f"parent job missing or has no output: {j.parent_job_id}"
                )
            parent_video = s.data_dir_abs / parent.output_path
            if not parent_video.exists():
                raise FileNotFoundError(f"parent video missing: {parent_video}")

            import imageio.v2 as imageio

            reader = imageio.get_reader(str(parent_video))
            try:
                meta = reader.get_meta_data()
                nframes = int(meta.get("nframes", 0)) if isinstance(meta, dict) else 0
                if nframes <= 0:
                    nframes = reader.count_frames()
            finally:
                reader.close()
            last_idx = max(0, int(nframes) - 1)

            reader = imageio.get_reader(str(parent_video))
            try:
                frame_arr = reader.get_data(last_idx)
            finally:
                reader.close()

            img = Image.fromarray(frame_arr)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            png_bytes = buf.getvalue()
            upload_path, sha = files.save_upload(j.user_id, png_bytes, ".png")
            new_upload_id = str(ulid.ULID())
            up_rec = Upload(
                id=new_upload_id,
                user_id=j.user_id,
                path=str(upload_path.relative_to(files.uploads_dir)),
                kind="image",
                sha256=sha,
            )
            db.add(up_rec)
            db.commit()

            params["image_upload_id"] = new_upload_id
            if "strength" not in params or params.get("strength") is None:
                params["strength"] = 0.6
            j.params_json = json.dumps(params)
            j.kind = "i2v"  # downstream treats this as an i2v job
            db.commit()

        progress_state = {"p": 0.0}

        def _on_step(step: int, total: int) -> None:
            j.stage = JobStage.denoising
            j.progress = step / total if total else 0.0
            # Throttle DB writes: every 5 steps or at the end.
            if step % 5 == 0 or step == total:
                db.commit()

        def _run_inference() -> bytes:
            j.stage = JobStage.denoising
            db.commit()
            # Resolve image_upload_id -> PIL.Image for i2v-style runs.
            image: Image.Image | None = None
            call_params = dict(params)
            upload_id = call_params.pop("image_upload_id", None)
            if upload_id:
                upload = db.get(Upload, upload_id)
                if upload is not None:
                    full_path = files.uploads_dir / upload.path
                    image = Image.open(full_path)
            mp4 = ltx_generate(
                pipeline=pm.get(),
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
        rel = str(out_path.relative_to(s.data_dir_abs))
        j.output_path = rel
        j.duration_sec = time.time() - t0
        j.status = JobStatus.succeeded
        j.finished_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        j.status = JobStatus.failed
        j.error = repr(e)[:2000]
        j.finished_at = datetime.now(timezone.utc)
        db.commit()


def _real_loader_for(model_id: str):
    """Return a ``loader(model_id) -> pipeline`` closure for ``model_id``.

    The ``LTXVideoPipeline.from_pretrained`` call lives inside the returned
    closure so it only fires when :meth:`PipelineManager.load` actually
    invokes the loader. This keeps the app importable even when the
    ``ltx_video`` package is not installed in the environment (the import
    is lazy). The closure ignores its ``model_id`` argument and uses the
    checkpoint path captured from the registry.
    """
    s = get_settings()
    reg = reg_mod.load(s.registry_path)
    entry = reg.by_id(model_id)
    if entry is None:
        raise RuntimeError(f"unknown model: {model_id}")
    ckpt = s.model_dir_abs / entry.checkpoint_path

    def _loader(_model_id: str):
        # Import lazily; LTX-Video is heavy and only loaded when needed.
        from ltx_video.pipelines.pipeline_ltx_video import LTXVideoPipeline
        return LTXVideoPipeline.from_pretrained(str(ckpt))

    return _loader