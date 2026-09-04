"""Asynchronous job queue with a single worker (MAX_CONCURRENT_JOBS=1).

The queue runs its worker in a background thread that owns its own asyncio
event loop. This lets callers interact with the queue from synchronous code
(e.g. FastAPI handlers) while the worker benefits from ``asyncio`` for I/O
concurrency and structured cancellation.

The worker holds an ``asyncio.Lock`` (``self._lifecycle_lock``) that guards
the call to :func:`app.core.job_runner.run`. This enforces the
``MAX_CONCURRENT_JOBS = 1`` policy at the coroutine level: even if multiple
worker tasks were ever started, only one job lifecycle (load + inference +
write) can be in flight at a time. ``PipelineManager`` already has a
``threading.Lock`` for thread-safety; the ``asyncio.Lock`` here prevents
two coroutines from racing on the pipeline state.
"""
from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

import ulid

from app.db.models import Job, JobStatus
from app.db.session import SessionLocal


class JobQueue:
    """A single-worker job queue with an asyncio lifecycle lock.

    The queue is safe to call from synchronous code: ``start``/``stop`` block
    on the background thread, and ``submit``/``status``/``cancel`` use the
    module-level ``SessionLocal`` session.
    """

    def __init__(self) -> None:
        self._q: asyncio.Queue[str] | None = None
        self._lifecycle_lock: asyncio.Lock | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready_event = threading.Event()
        self._stop_event = threading.Event()
        self._tasks: list[asyncio.Task] = []

    # ---- Lifecycle (sync, callable from any context) ----

    def start(self) -> None:
        """Start the background worker thread and event loop.

        Safe to call multiple times: subsequent calls are no-ops.
        """
        if self._thread is not None and self._thread.is_alive():
            return
        self._ready_event.clear()
        self._stop_event.clear()
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, name="JobQueueWorker", daemon=True
        )
        self._thread.start()
        # Block until the loop has installed the queue and lock.
        if not self._ready_event.wait(timeout=5):
            raise RuntimeError("JobQueue worker thread did not start in time")

    def stop(self) -> None:
        """Signal the worker to stop and join the background thread.

        Safe to call multiple times. ``stop`` is synchronous so it can be used
        from ``finally`` blocks in tests.
        """
        self._stop_event.set()
        if self._loop is not None and self._q is not None:
            # Wake the worker out of the wait_for so it can observe the stop.
            try:
                self._loop.call_soon_threadsafe(self._q.put_nowait, "__STOP__")
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._thread = None
        self._loop = None
        self._q = None
        self._lifecycle_lock = None
        self._tasks = []

    # ---- Public API (sync) ----

    def submit(
        self,
        *,
        kind: str,
        user_id: int,
        model_id: str,
        params: dict[str, Any],
        parent_job_id: str | None = None,
    ) -> str:
        """Insert a new job row and enqueue it for processing.

        Returns the job_id (ULID string).
        """
        job_id = str(ulid.ULID())
        with SessionLocal() as db:
            db.add(
                Job(
                    id=job_id,
                    user_id=user_id,
                    kind=kind,
                    model_id=model_id,
                    params_json=json.dumps(params),
                    parent_job_id=parent_job_id,
                )
            )
            db.commit()
        if self._loop is not None and self._q is not None:
            # Cross-thread enqueue. The DB write above is committed before
            # the job_id lands in the queue, so the worker can read it.
            asyncio.run_coroutine_threadsafe(self._q.put(job_id), self._loop)
        return job_id

    def status(self, job_id: str) -> Job | None:
        """Read the current state of a job from the DB."""
        with SessionLocal() as db:
            return db.get(Job, job_id)

    def cancel(self, job_id: str) -> bool:
        """Mark a queued job as cancelled. Returns True if the state changed."""
        with SessionLocal() as db:
            j = db.get(Job, job_id)
            if j is None or j.status != JobStatus.queued:
                return False
            j.status = JobStatus.cancelled
            db.commit()
            return True

    # ---- Internal: background event loop ----

    def _run_loop(self) -> None:
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        self._q = asyncio.Queue()
        self._lifecycle_lock = asyncio.Lock()
        self._ready_event.set()
        try:
            self._loop.run_until_complete(self._worker())
        finally:
            try:
                self._loop.close()
            except Exception:
                pass

    async def _worker(self) -> None:
        from app.core import job_runner

        assert self._q is not None
        assert self._lifecycle_lock is not None

        while not self._stop_event.is_set():
            try:
                job_id = await asyncio.wait_for(self._q.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                return

            if job_id == "__STOP__":
                self._q.task_done()
                return

            try:
                # MAX_CONCURRENT_JOBS = 1: the lifecycle lock serializes
                # load + inference + write across any future worker tasks.
                async with self._lifecycle_lock:
                    with SessionLocal() as db:
                        await job_runner.run(job_id, db)
            except Exception as e:
                with SessionLocal() as db:
                    j = db.get(Job, job_id)
                    if j is not None and j.status not in (
                        JobStatus.succeeded,
                        JobStatus.failed,
                        JobStatus.cancelled,
                    ):
                        j.status = JobStatus.failed
                        j.error = f"worker crashed: {e!r}"
                        db.commit()
            finally:
                self._q.task_done()


_singleton: JobQueue | None = None


def get_queue() -> JobQueue:
    """Return the process-wide :class:`JobQueue` singleton.

    The singleton is created lazily on first access. Callers that want a
    dedicated instance for tests should instantiate :class:`JobQueue`
    directly.
    """
    global _singleton
    if _singleton is None:
        _singleton = JobQueue()
    return _singleton
