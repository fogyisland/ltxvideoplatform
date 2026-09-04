# tests/integration/test_job_runner.py
"""End-to-end test for JobQueue + job_runner.

The test stubs ``app.core.pipeline_manager._singleton`` so the real LTX-Video
pipeline is never loaded. A small dummy checkpoint file is created so the
``_ensure_loaded`` step does not raise ``FileNotFoundError``.
"""
from __future__ import annotations

import time

import pytest

from app.db.models import Role, User
from app.auth.passwords import hash_password


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    from app.config import get_settings
    get_settings.cache_clear()
    # app.storage.files captures outputs_dir / uploads_dir at import time;
    # redirect them to tmp_path so the runner writes inside the test sandbox.
    from app.storage import files
    monkeypatch.setattr(files, "outputs_dir", tmp_path / "outputs")
    monkeypatch.setattr(files, "uploads_dir", tmp_path / "uploads")
    monkeypatch.setattr(files, "previews_dir", tmp_path / "previews")
    from app.db.session import Base, get_engine
    engine = get_engine()
    # Drop + recreate to guarantee a clean state (the default database
    # at ./data/app.db is persistent across test runs).
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    s = Session()
    u = User(username="u", password_hash=hash_password("p"), role=Role.user)
    s.add(u)
    s.commit()
    yield s
    s.close()


def test_job_runs_to_succeeded(db_session, monkeypatch, tmp_path):
    # ---- Patch pipeline_manager to bypass LTX-Video ----
    from app.core import pipeline_manager as pm

    pm._singleton = pm.PipelineManager()
    # Noop load: the pipeline is already installed below.
    pm._singleton.load = (
        lambda mid, loader=None: pm._singleton._pipeline
        or pm._singleton._pipeline.__init__()
        or None
    )

    class _Stub:
        def __call__(self, **kw):
            from PIL import Image
            return [Image.new("RGB", (8, 8)) for _ in range(2)]

    pm._singleton._pipeline = _Stub()
    pm._singleton._current_id = "mock"

    # ---- Create a dummy checkpoint so _ensure_loaded does not raise ----
    from app.config import get_settings
    s = get_settings()
    ckpt = s.model_dir_abs / "ltx-video-2b-distilled" / "model.safetensors"
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    ckpt.write_bytes(b"")

    # ---- Submit a job and poll for completion ----
    from app.core import job_queue as jq
    from app.core import job_runner as jr  # noqa: F401  (ensures module is importable)

    q = jq.JobQueue()
    q.start()
    try:
        job_id = q.submit(
            kind="t2v",
            user_id=db_session.query(User).first().id,
            model_id="ltx-2b-distilled",
            params={
                "prompt": "x",
                "num_frames": 9,
                "height": 32,
                "width": 32,
                "num_inference_steps": 2,
                "guidance_scale": 5.0,
                "seed": 0,
                "fps": 8,
            },
        )
        # Poll up to ~6s for the worker to finish the job.
        j = None
        for _ in range(60):
            j = q.status(job_id)
            if j is not None and j.status.value in ("succeeded", "failed"):
                break
            time.sleep(0.1)
        assert j is not None, "job not found"
        assert j.status.value == "succeeded", f"got {j.status.value}: {j.error}"
    finally:
        q.stop()
