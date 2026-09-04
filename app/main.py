# app/main.py (FastAPI for Task 7; Gradio UI shim added in Task 8)
from __future__ import annotations
from fastapi import FastAPI

def build_app() -> FastAPI:
    from app.api import auth, models, uploads, generation, jobs, history, files as files_api
    app = FastAPI(title="LTX-Video Web Platform", version="0.1.0")
    app.include_router(auth.router)
    app.include_router(models.router)
    app.include_router(uploads.router)
    app.include_router(generation.router)
    app.include_router(jobs.router)
    app.include_router(history.router)
    app.include_router(files_api.router)
    return app


def build_gradio_app(launch: bool = True):
    """Lazily import the Gradio UI so the FastAPI app doesn't pay the import cost.

    Returns ``(blocks, port)`` where ``blocks`` is a ``gr.Blocks`` instance. When
    ``launch`` is False the server is not started — useful for smoke tests and
    for callers that want to embed the Blocks somewhere else.
    """
    from app.ui.gradio_app import build_gradio_app as _build
    return _build(launch=launch)
