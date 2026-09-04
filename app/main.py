# app/main.py (stub for Task 7; full impl in Task 11)
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
