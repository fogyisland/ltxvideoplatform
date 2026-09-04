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
import json
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import pipeline_manager as pm_mod
from app.core import registry as reg_mod
from app.core.ltx_wrappers import generate as ltx_generate
from app.db.models import Job, JobStage, JobStatus
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
        # Real loader wiring (uses LTXVideoPipeline.from_pretrained) — see Task 9
        pm.load(model_id, loader=_real_loader(str(ckpt)))

    try:
        await asyncio.wait_for(
            asyncio.to_thread(_ensure_loaded, j.model_id),
            timeout=s.job_timeout_sec,
        )

        params = json.loads(j.params_json)
        j.stage = JobStage.encoding
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
            mp4 = ltx_generate(
                pipeline=pm.get(),
                kind=j.kind,
                on_step=_on_step,
                **params,
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


def _real_loader(checkpoint_path: str):
    """Return a ``loader(model_id) -> pipeline`` closure.

    Task 9 will wire this to the real ``LTXVideoPipeline.from_pretrained``
    call. The closure must accept a ``model_id`` argument because
    :meth:`PipelineManager.load` invokes ``loader(model_id)``.
    """

    def _loader(model_id: str):
        # Import lazily; LTX-Video is heavy and only loaded when needed.
        from ltx_video.pipelines.pipeline_ltx_video import LTXVideoPipeline
        return LTXVideoPipeline.from_pretrained(checkpoint_path)

    return _loader
