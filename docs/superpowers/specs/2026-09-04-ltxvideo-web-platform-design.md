# LTX-Video Web Platform — Design

**Date:** 2026-09-04
**Status:** Draft (awaiting user approval)
**Author:** brainstorming session

## 1. Summary

A web platform that wraps the open-source [LTX-Video](https://github.com/Lightricks/LTX-Video) model
into a usable product for a small team (≤5 users) on a single GPU host. Users interact through a
Gradio UI and/or a REST API. The platform supports the distilled LTX-Video variants out of the
box (`ltx-13b-distilled`, `ltx-13b-distilled-fast`, `ltx-13b-distilled-long-multi-shot`,
`ltx-2b-distilled`), with the full `ltx-13b-full` checkpoint available behind an "advanced"
toggle. Four generation modes: text-to-video, image-to-video (first-frame conditioning),
multi-keyframe guidance, and long-video composition (sliding-window + last-frame extension).
LoRA composition is deferred (see R3).

**Primary path:** GPU/CUDA inference. CPU is not a supported target.

## 2. Goals and Non-Goals

### Goals
- G1. Web UI for T2V / I2V / keyframe / long-video generation
- G2. Support LTX-Video distilled variants out of the box; `ltx-13b-full` available behind an
  "advanced" toggle. LoRA composition is out of scope (R3).
- G3. Lightweight auth (token) with per-user history (SQLite)
- G4. Async job queue with progress + preview frames
- G5. Model hot-swap (load / unload / switch) on a single GPU without restarting the process
- G6. Two-stage upscale (low-res → hi-res) for higher quality
- G7. Long-video via sliding window (`long-multi-shot` checkpoint) and last-frame extension
- G8. REST API usable from scripts (CI, batch jobs)
- G9. Single-machine deployment via one command (`python -m app.main`)

### Non-Goals (YAGNI)
- N1. Multi-GPU / distributed inference (architecture leaves an extension hook; not built now)
- N2. Multi-tenant SaaS billing / quotas (single team, no per-user billing)
- N3. Public sharing / social features
- N4. Mobile-native apps
- N5. CPU inference (LTX-Video is GPU-bound; CPU would take hours per clip and provide no value)
- N6. Real-time video streaming generation (LTX-Video is offline-batch)
- N7. Model fine-tuning UI (training is out of scope)

## 3. Architecture

```
Browser (≤5 users)
   │   HTTPS + JWT
   ▼
┌──────────────────────────────┐
│ Gradio UI (port 7860)        │ ← primary UI
│  + auth dependency on        │
│    FastAPI user table        │
└──────────┬───────────────────┘
           │ httpx (localhost)
           ▼
┌──────────────────────────────┐
│ FastAPI backend (port 8000)  │ ← REST API
│  /api/v1/{auth,jobs,models,  │
│          history,uploads}    │
└──────────┬───────────────────┘
           │ asyncio.Queue
           ▼
┌──────────────────────────────┐
│ InferenceWorker (singleton)  │
│  - pipeline_manager          │
│  - job_runner                │
│  - ltx_wrappers              │
└──────────┬───────────────────┘
           │
           ▼
       CUDA GPU (single)
           │
           ▼
       data/outputs/{user}/{job}.mp4
```

Single process (`uvicorn` for FastAPI; Gradio runs on a background thread). Both share the same
SQLAlchemy session factory and pipeline_manager singleton.

### 3.1 Module layout

```
app/
├── main.py                # uvicorn + gradio bootstrap
├── config.py              # pydantic-settings
├── auth/{jwt,passwords,deps}.py
├── api/{auth,jobs,models,history,uploads}.py
├── core/
│   ├── pipeline_manager.py    # singleton; load/unload/swap
│   ├── job_queue.py           # asyncio.Queue + 1 worker
│   ├── job_runner.py          # execute one job end-to-end
│   └── ltx_wrappers.py        # LTXVideoPipeline + LTXI2VLongMultiPromptPipeline
├── db/{models,session}.py + migrations/
├── storage/files.py
└── ui/{gradio_app,components}.py

scripts/download_models.py
models/registry.yaml
models/                  # .safetensors + YAML (downloaded or symlinked)
data/                    # runtime: app.db, uploads/, outputs/, previews/, logs/
tests/                   # unit / integration / e2e / contract
```

### 3.2 Module contracts

| Module | Responsibility | Public interface | Depends on |
|---|---|---|---|
| `pipeline_manager` | Own the loaded `LTXVideoPipeline`; load / unload / swap; track VRAM; lock | `load(model_id)`, `unload()`, `get()`, `current_id`, `status()`, `lock` | `ltx_video`, torch |
| `job_queue` | Single-worker async queue; submit / status / cancel | `submit(req) → job_id`, `status(id)`, `cancel(id)` | DB |
| `job_runner` | One inference end-to-end: load model → run pipeline → write output → update DB | `run(job_id, req)` | `pipeline_manager`, `storage`, `ltx_wrappers`, DB |
| `ltx_wrappers` | Normalize LTX call signatures; handle progress callback | `generate(req, on_step)` | `ltx_video` |
| `auth` | Login → JWT; middleware | `login(u,p) → token`, `current_user` | DB, jose, passlib |
| `db` | Persistence | SQLAlchemy models + SessionLocal | — |
| `storage` | Per-user path resolution; upload / output / preview writes; ownership check | `resolve(uid, kind, name)`, `save_*`, `verify_owner` | `config` |
| `ui` | Gradio blocks; calls FastAPI; displays history | `build_app() → gr.Blocks` | all |
| `api` | REST routes; depends on `core` + `auth` + `db` | routers | all |

## 4. Data Model (SQLAlchemy / SQLite)

```python
class User:
    id: int  # PK
    username: str  # unique
    password_hash: str
    role: str  # "admin" | "user"
    is_active: bool
    created_at: datetime

class Model:
    """Metadata for a registered model variant."""
    id: str  # PK, e.g. "ltx-13b-distilled-fast"
    display_name: str
    kind: str  # "t2v_distilled" | "t2v_full" | "i2v_long" | "lora"
    checkpoint_path: str  # relative to MODEL_DIR
    config_path: str
    default_steps: int
    default_frames: int
    vram_gb: int
    enabled: bool
    description: str

class Job:
    id: str  # ULID PK
    user_id: int  # FK
    kind: str  # "t2v" | "i2v" | "keyframe" | "extend" | "upscale" | "model_load"
    model_id: str  # FK to Model.id
    params_json: str  # full request payload
    status: str  # "queued" | "running" | "succeeded" | "failed" | "cancelled"
    progress: float  # 0..1
    stage: str  # "loading_model" | "encoding" | "denoising" | "decoding" | "writing"
    error: str | None
    output_path: str | None  # relative to data/outputs
    preview_path: str | None  # most recent preview frame
    parent_job_id: str | None  # for extend / upscale chains
    duration_sec: float | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

class Upload:
    id: str  # PK
    user_id: int  # FK
    path: str  # relative to data/uploads
    kind: str  # "image" | "video"
    sha256: str
    created_at: datetime
```

## 5. REST API

All endpoints under `/api/v1`. Auth via `Authorization: Bearer <JWT>`. JSON in / out except uploads.

### 5.1 Auth
- `POST /auth/login` `{username, password}` → `{access_token, expires_in}`
- `GET /auth/me` → `{id, username, role}`

### 5.2 Models
- `GET /models` → `Model[]`
- `GET /models/current` → `Model | null`
- `POST /models/{id}/load` → `202 {job_id}` (model-load job)
- `POST /models/unload` → `202 {job_id}`

### 5.3 Generation

All generation endpoints return `202 {job_id}`. Each endpoint accepts a JSON body. Fields shared
across endpoints: `model_id`, `prompt`, `negative_prompt?`, `num_frames`, `height`, `width`,
`num_inference_steps`, `guidance_scale`, `seed?`, `fps?`. Frame counts must satisfy `8n+1`;
resolution must be divisible by 32.

**`POST /t2v`** — text-to-video. Required: `model_id`, `prompt`. Optional long-video fields
below.

**`POST /i2v`** — image-to-video. Adds required `image_upload_id` and optional `strength`
(0.0–1.0, default 0.85).

**`POST /keyframe`** — multi-keyframe guidance. Adds required `frame_uploads: [{upload_id,
frame_index, strength}]` (≥ 1 entry).

**`POST /extend`** — last-frame extension. Adds required `parent_job_id` and optional
`extra_frames`, `strength`.

**`POST /upscale`** — stage-2 hi-res of an existing low-res job. Adds required `parent_job_id`.

**Long-video fields** (T2V / I2V when `model_id` resolves to a long-multishot variant):
`temporal_tile_size` (default 80), `temporal_overlap` (default 24). The `prompt` may contain
`|`-separated segments mapped to windows.

**Two-stage fields**: any T2V / I2V may include `"two_stage": true` to first generate at half
resolution then upscale via the parent's pipeline (the upscale sub-job is queued automatically).

Full example (long-multishot T2V):
```jsonc
{
  "model_id": "ltx-13b-distilled-long-multi-shot",
  "prompt": "a chimpanzee walks through jungle | chimpanzee sits",
  "num_frames": 161,
  "height": 480, "width": 768,
  "num_inference_steps": 30,
  "guidance_scale": 5.0,
  "seed": 42,
  "fps": 24,
  "temporal_tile_size": 80,
  "temporal_overlap": 24
}
```

### 5.4 Job introspection
- `GET /jobs/{id}` → `Job` (full)
- `GET /jobs/{id}/result` → `302` to `/files/outputs/...` once succeeded
- `POST /jobs/{id}/cancel` → `{ok}`
- `GET /jobs/{id}/preview` → most-recent PNG (decoded latent snapshot)

### 5.5 History
- `GET /history?limit=20&offset=0&kind=t2v` → `JobSummary[]`
- `GET /history/{id}` → `Job`
- `DELETE /history/{id}` → `{ok}` (deletes record and file)

### 5.6 Uploads
- `POST /uploads` (multipart `image/*` or `video/*`) → `{id, path, sha256}`
- `GET /files/{path:path}` (auth-checked; path must start with `uploads/{user_id}/` or
  `outputs/{user_id}/`)

## 6. Job Lifecycle

```
submit  ─► create Job(queued)  ─► enqueue
                                       │
                                       ▼
                              worker picks (FOR UPDATE)
                                       │
                              status=running, started_at=now
                                       │
                                       ▼
                       pipeline_manager.ensure_loaded(model_id)
                                       │
                       ltx_wrappers.generate(on_step=...)
                                       │
                       write .mp4  ─► status=succeeded
```

### 6.1 Concurrency
- Single worker (`MAX_CONCURRENT_JOBS=1`, default). Documented constraint: one inference at a
  time on one GPU.
- `pipeline_manager` uses `threading.Lock` (inference runs in worker thread) + `asyncio.Lock`
  (job lifecycle). No two inferences share the GPU.
- Two model-load requests serialize on the same lock.

### 6.2 Progress
- Two mechanisms (no SSE in MVP):
  1. Gradio `gr.Progress(track_tqdm=True)` via step callback.
  2. DB poll `GET /jobs/{id}` every 1 s from frontend.
- Preview frames: every 5 denoising steps, decode current latent → PNG → `data/previews/{job_id}/`.
  Surface via `GET /jobs/{id}/preview` (returns the latest).

### 6.3 Long-video
- `LTXI2VLongMultiPromptPipeline` handles sliding windows internally.
- Prompts separated by `|` are split platform-side; the worker computes
  `num_windows = ceil(num_frames / (tile_size - overlap))` and assigns prompts.
- `ltx-video-13b-distilled-long-multi-shot` checkpoint is registered as a model.

### 6.4 Last-frame extension
- Read parent's `output_path`; extract last frame via ffmpeg.
- Save as a new `Upload` (image) under the same user.
- Submit an I2V job with `image_upload_id` of the last frame and `parent_job_id` set.

## 7. Error Handling

| Failure | Behavior |
|---|---|
| Model file missing | Startup + load time check; `400` with explicit path |
| `torch.cuda.OutOfMemoryError` | Auto `torch.cuda.empty_cache()` + one retry at lower resolution; on second OOM: `status=failed`, `error` includes `torch.cuda.mem_get_info()` snapshot |
| Inference timeout (`JOB_TIMEOUT_SEC=1800`) | `asyncio.wait_for` wraps the run; `status=failed`, `error="timeout"` |
| Cancellation | Worker checks cancel flag between steps; sets `status=cancelled` and exits |
| Disk < `OUTPUT_DISK_MIN_FREE_GB` | Reject new submissions with `507 Insufficient Storage` |
| Token expired | `401` from API; Gradio UI redirects to login |
| Path traversal in `GET /files/{path}` | `verify_owner` rejects; `403` |
| Bad parameters (e.g. height not divisible by 32) | `400` with explicit message; do not enqueue |

## 8. Configuration

`.env` (loaded via pydantic-settings):

```
APP_HOST=0.0.0.0
APP_PORT_API=8000
APP_PORT_GRADIO=7860
DEVICE=cuda                          # only "cuda" supported in MVP
DATA_DIR=./data
MODEL_DIR=./models
REGISTRY_PATH=./models/registry.yaml
DATABASE_URL=sqlite:///./data/app.db
JWT_SECRET=<32+ random chars>
JWT_EXPIRES_MIN=720
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<set on first run, prompted if blank>
MAX_CONCURRENT_JOBS=1
JOB_TIMEOUT_SEC=1800
OUTPUT_DISK_MIN_FREE_GB=5
LOG_LEVEL=INFO
HF_TOKEN=                             # for private models
```

Startup validation: CUDA available; registry parses; `MODEL_DIR` exists; disk free; admin user
exists (created if missing and `ADMIN_PASSWORD` is set, otherwise the server refuses to start and
prompts).

## 9. Model Registry

`models/registry.yaml`:

```yaml
models:
  - id: ltx-13b-distilled-fast
    display_name: "LTX-Video 13B Distilled Fast (8x)"
    kind: t2v_distilled
    checkpoint_path: ltx-video-13b-distilled-fast/ltxv-13b-256-distilled.safetensors
    config_path: ltx-video-13b-distilled-fast/ltxv-13b-256-distilled.yaml
    default_steps: 8
    default_frames: 121
    vram_gb: 16
    enabled: true
  - id: ltx-13b-distilled
    display_name: "LTX-Video 13B Distilled (Standard)"
    kind: t2v_distilled
    checkpoint_path: ltx-video-13b-distilled/ltxv-13b-256-distilled.safetensors
    config_path: ltx-video-13b-distilled/ltxv-13b-256-distilled.yaml
    default_steps: 20
    default_frames: 121
    vram_gb: 16
    enabled: true
  - id: ltx-13b-distilled-long-multi-shot
    display_name: "LTX-Video 13B Long Multi-Shot"
    kind: i2v_long
    checkpoint_path: ltx-video-13b-distilled-long-multi-shot/model.safetensors
    config_path: ltx-video-13b-distilled-long-multi-shot/config.yaml
    default_steps: 30
    default_frames: 161
    vram_gb: 20
    enabled: true
  - id: ltx-2b-distilled
    display_name: "LTX-Video 2B Distilled"
    kind: t2v_distilled
    checkpoint_path: ltx-video-2b-distilled/model.safetensors
    config_path: ltx-video-2b-distilled/config.yaml
    default_steps: 8
    default_frames: 97
    vram_gb: 6
    enabled: true
  - id: ltx-13b-full
    display_name: "LTX-Video 13B Full (no distill)"
    kind: t2v_full
    checkpoint_path: ltx-video-13b-full/ltxv-13b-256-full.safetensors
    config_path: ltx-video-13b-full/ltxv-13b-256-full.yaml
    default_steps: 40
    default_frames: 121
    vram_gb: 28
    enabled: false                  # advanced toggle
```

`scripts/download_models.py` resolves HF repo paths and downloads via `huggingface-cli`,
then symlinks / verifies the expected paths in `models/`.

## 10. Storage Layout

```
data/
├── app.db
├── uploads/{user_id}/{ulid}.{ext}
├── outputs/{user_id}/{job_id}.mp4
├── previews/{job_id}/step_NNN.png
└── logs/app.log
```

Per-user isolation enforced by `storage.files.resolve(uid, kind, name)`. Public path endpoints
verify ownership before serving.

## 11. UI (Gradio)

Tabs:
1. **Generate** — sub-tabs for T2V / I2V / Keyframe / Long-video / Upscale. Each shows:
   - Model selector (filtered by capability)
   - Prompt + negative prompt
   - Parameter panel (steps, frames, h/w, CFG, seed, fps; advanced collapsed by default)
   - Upload area (for I2V / keyframe)
   - Submit button → progress bar → video player
2. **Models** — list, load / unload, current model indicator, VRAM estimate
3. **History** — list of past jobs (filter by kind / model / date), click to view + replay params
4. **Account** — change password, logout

Gradio runs in a daemon thread (`prevent_thread_lock=True`); main process runs uvicorn.

## 12. Testing

| Layer | Coverage | Tool |
|---|---|---|
| Unit | `auth`, `pipeline_manager` (mocked pipeline), `storage`, `job_runner` (mocked pipeline) | pytest |
| Integration | API end-to-end: login → submit → poll → result, all kinds | pytest + httpx.AsyncClient |
| Long-video split | prompt split + window math | pytest |
| E2E UI | Gradio client triggers a generation; assert file appears | pytest + gradio_client |
| Real GPU smoke | 2B distilled, 2 steps, 9 frames; ~5 s | pytest `@pytest.mark.gpu` |
| Contract | OpenAPI schema enforced | schemathesis |

CI uses mocks; full E2E runs only when GPU + models present.

## 13. Deployment

Single command: `python -m app.main`.

Prerequisites: NVIDIA driver, CUDA 12.x, Python 3.11+, ≥16 GB VRAM for 13B distilled
(≥24 GB recommended for 13B full).

Out-of-scope: Docker, systemd, multi-host. Hooks left in `app/main.py` and `pyproject.toml` for
future containerization.

## 14. Risks and Open Questions

- **R1.** LTX-Video Python API surface may differ slightly from documented `from_pretrained`
  signature; `ltx_wrappers` is the choke point that absorbs these differences. Spike during
  implementation to confirm.
- **R2.** Long-video sliding-window memory: `num_frames=161, tile=80, overlap=24` should fit on
  24 GB; longer chains may OOM. User must stay under the recommended limits; UI warns when over.
- **R3.** LoRA composition (distill + iclorax + spatial-up stacked) is not in MVP; the registry
  supports `kind: lora` but UI doesn't yet expose LoRA selection. Tracked as a follow-up.
- **R4.** The `long-multi-shot` checkpoint's exact HF path / filename needs to be confirmed
  against the LTX-Video 0.9.8 release assets during implementation.

## 15. References

- [LTX-Video GitHub](https://github.com/Lightricks/LTX-Video)
- [LTX-Video 0.9.8 + 13B announcement](https://ltx.io/blog/ltx-video-9-8-and-13b-announcement)
- [LTX-Video 13B distilled models blog](https://ltx.io/blog/ltx-video-13b-distilled)
- [LTX-Video model cards](https://ltx.io/model-cards)
- [LTX-Video paper (arXiv 2501.00103)](https://arxiv.org/abs/2501.00103) — per-token timestep
  conditioning, I2V first-frame mechanism
- [ComfyUI-LTXVideo](https://github.com/logtd/ComfyUI-LTXVideo) — community integration reference
- [LTX-Video I2V docs](https://docs.ltx.video/open-source-model/usage-guides/image-to-video)
