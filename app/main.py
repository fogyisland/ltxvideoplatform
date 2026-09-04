# app/main.py (FastAPI for Task 7; Gradio UI shim added in Task 8;
# startup bootstrap + uvicorn entrypoint added in Task 9.)
from __future__ import annotations

import logging
import threading

import uvicorn
from fastapi import FastAPI


def build_app() -> FastAPI:
    from app.api import auth, models, uploads, generation, jobs, history, files as files_api, admin as admin_api

    app = FastAPI(title="LTX-Video Web Platform", version="0.1.0")
    app.include_router(auth.router)
    app.include_router(models.router)
    app.include_router(uploads.router)
    app.include_router(generation.router)
    app.include_router(jobs.router)
    app.include_router(history.router)
    app.include_router(files_api.router)
    app.include_router(admin_api.router)
    return app


def build_gradio_app(launch: bool = True):
    """Lazily import the Gradio UI so the FastAPI app doesn't pay the import cost.

    Returns ``(blocks, port)`` where ``blocks`` is a ``gr.Blocks`` instance. When
    ``launch`` is False the server is not started — useful for smoke tests and
    for callers that want to embed the Blocks somewhere else.
    """
    from app.ui.gradio_app import build_gradio_app as _build

    return _build(launch=launch)


def _bootstrap() -> None:
    """One-shot startup: directories, CUDA check, schema, admin seed, registry seed.

    Order matters:
      1. data dirs — must exist before anything else writes there.
      2. CUDA check — refusing to start is better than crashing mid-job.
      3. ``Base.metadata.create_all`` — idempotent; safe across restarts.
      4. Admin user — only created if missing; password may be empty.
      5. Registry rows — upserted from ``models/registry.yaml`` so the DB
         mirrors the canonical 5-model set.
    """
    # Lazy imports keep ``build_app()`` importable without side effects.
    import torch

    from app.auth.passwords import hash_password
    from app.config import get_settings
    from app.core import job_queue as jq
    from app.core.registry import load as load_registry
    from app.db.models import Model as ModelRow
    from app.db.models import Role, User
    from app.db.session import Base, SessionLocal, get_engine

    s = get_settings()

    # 1. data dirs
    s.data_dir_abs.mkdir(parents=True, exist_ok=True)
    s.uploads_dir.mkdir(parents=True, exist_ok=True)
    s.outputs_dir.mkdir(parents=True, exist_ok=True)
    s.previews_dir.mkdir(parents=True, exist_ok=True)

    # 2. CUDA check
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA not available; this app requires a GPU.")

    # 3. schema
    Base.metadata.create_all(get_engine())

    # 4. admin user
    if s.admin_password:
        with SessionLocal() as db:
            existing = db.query(User).filter_by(username=s.admin_username).first()
            if existing is None:
                db.add(
                    User(
                        username=s.admin_username,
                        password_hash=hash_password(s.admin_password),
                        role=Role.admin,
                        is_active=True,
                    )
                )
                db.commit()
    else:
        logging.warning(
            "ADMIN_PASSWORD is empty; skipping admin user seed."
        )

    # 5. registry rows (upsert by primary key)
    reg = load_registry(s.registry_path)
    with SessionLocal() as db:
        for e in reg.models:
            row = db.get(ModelRow, e.id)
            data = e.__dict__
            if row is None:
                db.add(ModelRow(**data))
            else:
                for k, v in data.items():
                    setattr(row, k, v)
        db.commit()


def main() -> None:
    """Process entrypoint: bootstrap, queue, Gradio thread, uvicorn."""
    from app.config import get_settings
    from app.core import job_queue as jq

    logging.basicConfig(level=get_settings().log_level)
    _bootstrap()
    jq.get_queue().start()

    app = build_app()
    s = get_settings()

    # Gradio on a daemon thread — it never blocks uvicorn.
    def _gradio():
        build_gradio_app(launch=True)

    threading.Thread(target=_gradio, name="GradioUI", daemon=True).start()

    uvicorn.run(
        app,
        host=s.app_host,
        port=s.app_port_api,
        log_level=s.log_level.lower(),
    )


if __name__ == "__main__":
    main()