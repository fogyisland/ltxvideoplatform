# Manual Verification Guide (GPU host required)

This document is the operator-facing smoke test for the LTX-Video Web Platform.
It must be executed on a machine with a CUDA-capable GPU.

> **NOTE — what this env verified vs. what you must do here.**
> The controller that produced this repository has no CUDA, no `LTX-Video`
> source tree, and no model checkpoints. The non-GPU portions of the test plan
> have been executed there (app imports, 32-test unit/integration suite,
> expected CUDA `RuntimeError`). Everything in this document must be executed
> on a real GPU host.

---

## 1. Prerequisites

| Component        | Requirement                                                  |
|------------------|--------------------------------------------------------------|
| OS               | Linux x86_64 (Ubuntu 22.04 LTS recommended)                  |
| GPU driver       | NVIDIA proprietary driver 535+ (matches CUDA 12.x)           |
| CUDA toolkit     | CUDA 12.1+ (system or runfile; the conda/cudnn pair is fine) |
| Python           | 3.11 or 3.12                                                 |
| Disk             | >= 60 GB free (models + outputs + cache)                     |
| VRAM (13B fast / 13B distilled)   | >= 16 GB (RTX 4080 / A5000-class)        |
| VRAM (13B distilled long multi-shot) | >= 20 GB                                  |
| VRAM (2B distilled) | >= 6 GB                                                   |
| VRAM (13B full, advanced toggle)    | >= 24 GB (recommended 28 GB)            |
| Hugging Face account | Optional, but needed for gated/private model mirrors    |

Tip: `nvidia-smi` should list the card and `nvcc --version` should report
CUDA 12.x before you continue.

---

## 2. Install

```bash
# 1. clone + editable install of the platform itself
git clone <this-repo-url> ltxvideo-web
cd ltxvideo-web
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .

# 2. LTX-Video (the upstream library this platform wraps)
pip install git+https://github.com/Lightricks/LTX-Video.git

# 3. CUDA build of PyTorch — pick the wheel that matches your driver.
#    (PyTorch's official CUDA 12.1 build is the most compatible.)
pip install --upgrade \
    torch torchvision --index-url https://download.pytorch.org/whl/cu121

# 4. dev tools (only needed if you intend to run the test suite)
pip install -e ".[dev]"
```

Quick sanity check:

```bash
python -c "import torch; print(torch.cuda.is_available(), torch.version.cuda)"
# expected: True 12.1
```

---

## 3. Download model checkpoints

`scripts/download_models.py` is the canonical fetcher. It reads
`models/registry.yaml` and uses `huggingface_hub.snapshot_download` with
allow-patterns scoped per model.

```bash
# Smallest model — fine for a smoke test on a 16 GB card
python scripts/download_models.py --model ltx-2b-distilled

# Or everything that is enabled in the registry
python scripts/download_models.py --all
```

Models land under `./models/<entry.folder>/...` (resolved from
`MODEL_DIR` / `./models`). For `--offline` validation against a pre-populated
disk, use `--offline`.

VRAM budget by id (from `models/registry.yaml`):

| id                                    | vram_gb | enabled | kind        |
|---------------------------------------|---------|---------|-------------|
| `ltx-13b-distilled-fast`              | 16      | yes     | t2v_distilled |
| `ltx-13b-distilled`                   | 16      | yes     | t2v_distilled |
| `ltx-13b-distilled-long-multi-shot`   | 20      | yes     | i2v_long      |
| `ltx-2b-distilled`                    | 6       | yes     | t2v_distilled |
| `ltx-13b-full`                        | 28      | no      | t2v_full      |

---

## 4. Boot sequence

```bash
cp .env.example .env
# edit .env:
#   JWT_SECRET=<32-or-more random chars>
#   ADMIN_PASSWORD=<a real password>
#   (leave the rest at defaults for the smoke)

python -m app.main
```

Expected log lines, in order:

1. CUDA-visible confirmation (implicit in `_bootstrap()` not raising).
2. Admin user created (only on first boot, when `User` row is missing).
3. `models/registry.yaml` upserted into the DB (5 rows; `ltx-13b-full` is
   `enabled: false`).
4. Job queue thread started.
5. Gradio UI bound on `0.0.0.0:7860` (from a daemon thread).
6. Uvicorn bound on `0.0.0.0:8000`.

If `_bootstrap()` raises `RuntimeError("CUDA not available; this app requires a GPU.")`
the process exits non-zero. That is the expected behaviour on a non-GPU host.

---

## 5. Web UI smoke (Step 2 of the task brief)

1. Open <http://localhost:7860>.
2. Log in as `admin` / `<ADMIN_PASSWORD>`.
3. Switch to the **T2V** tab.
4. Pick model `ltx-2b-distilled` (or whatever you downloaded).
5. Prompt: `a cat playing piano`.
6. Frames: `9`, steps: `4`, resolution: `128x128`.
7. Click **Generate**.

Expected: the progress bar advances through the denoising stages and a
playable `mp4` appears in the video player within ~30 s on a single consumer
GPU. Long-video variants (`ltx-13b-distilled-long-multi-shot`) and the
13B-full variant are surfaced only behind the **Advanced** toggle.

---

## 6. API smoke (Step 3 of the task brief — copy-pasteable)

```bash
# 1. Trade username/password for a bearer token.
TOK=$(curl -s -d "username=admin&password=$ADMIN_PASSWORD" \
        http://127.0.0.1:8000/api/v1/auth/login \
      | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2. List the model registry as JSON.
curl -s http://127.0.0.1:8000/api/v1/models \
     -H "Authorization: Bearer $TOK" | python -m json.tool
```

Expected: a JSON array with one object per registry entry, each containing
`id`, `display_name`, `kind`, `default_steps`, `default_frames`, `vram_gb`,
`enabled`, `description`.

Two more useful calls once the smoke passes:

```bash
# Authenticated who-am-I?
curl -s http://127.0.0.1:8000/api/v1/auth/me \
     -H "Authorization: Bearer $TOK" | python -m json.tool

# Currently loaded model + VRAM.
curl -s http://127.0.0.1:8000/api/v1/models/current \
     -H "Authorization: Bearer $TOK" | python -m json.tool
```

---

## 7. Cleanup / next-iteration

- On a successful smoke, tag the release:

  ```bash
  git tag v0.1.0-mvp
  ```

- To stop the server: `Ctrl+C` in the foreground process. The Gradio daemon
  thread is killed when uvicorn exits.
- Data persists under `./data/` (uploads, outputs, previews, `app.db`).
  Delete that directory for a clean re-boot.

---

## 8. What was *not* verified in the controller environment

The instructions above are written for a real GPU host. The non-GPU host
that produced this document only verified:

- `python -c "import app.main; print('OK')"` — app imports cleanly.
- `python -c "from app.main import _bootstrap; _bootstrap()"` — exits with
  `RuntimeError("CUDA not available; this app requires a GPU.")` as designed.
- `pytest tests/ -v -m "not gpu"` — `32 passed, 2 deselected, 17 warnings`.
  The two deselected tests are the `gpu`-marked real-GPU smoke at
  `tests/e2e/test_real_gpu.py`.

If anything in sections 1-7 above fails on your GPU host, capture the full
traceback (set `LOG_LEVEL=DEBUG` in `.env` first) and file an issue against
this repository.