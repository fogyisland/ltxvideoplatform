# LTX-Video Web Platform

Wraps [LTX-Video](https://github.com/Lightricks/LTX-Video) in a Gradio + FastAPI web app.

## Quick start (CPU smoke only — full usage requires GPU)

1. `pip install -e .`
2. `cp .env.example .env` and set `JWT_SECRET` to 32+ random chars.
3. `python -m app.main` (UI on :7860, API on :8000).

See `docs/superpowers/specs/2026-09-04-ltxvideo-web-platform-design.md` for the design.
