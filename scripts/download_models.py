# scripts/download_models.py
from __future__ import annotations
import argparse
import hashlib
import shutil
from pathlib import Path

from huggingface_hub import snapshot_download
from app.config import get_settings
from app.core.registry import load


HF_REPO = "Lightricks/LTX-Video"


def download_one(entry_id: str, offline: bool) -> int:
    settings = get_settings()
    reg = load(settings.registry_path)
    entry = reg.by_id(entry_id)
    if entry is None:
        raise SystemExit(f"unknown model: {entry_id}")

    target_dir = settings.model_dir_abs / Path(entry.checkpoint_path).parent
    target_dir.mkdir(parents=True, exist_ok=True)

    if offline:
        ckpt = settings.model_dir_abs / entry.checkpoint_path
        cfg = settings.model_dir_abs / entry.config_path
        if not ckpt.exists() or not cfg.exists():
            raise SystemExit(f"missing files for {entry_id}: {ckpt} / {cfg}")
        print(f"[offline] ok: {entry_id}")
        return 0

    snapshot_download(
        repo_id=HF_REPO,
        local_dir=str(settings.model_dir_abs),
        token=settings.hf_token or None,
        allow_patterns=[
            f"{Path(entry.checkpoint_path).parent}/**",
            f"{Path(entry.config_path).parent}/**",
        ],
    )
    print(f"downloaded: {entry_id} -> {target_dir}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--model", help="model id to download")
    g.add_argument("--all", action="store_true", help="download all enabled models")
    g.add_argument("--offline", action="store_true", help="verify only, no download")
    args = p.parse_args()

    settings = get_settings()
    reg = load(settings.registry_path)

    if args.model:
        return download_one(args.model, offline=False)
    if args.offline:
        rc = 0
        for m in reg.enabled_ids():
            rc |= download_one(m, offline=True)
        return rc
    if args.all:
        rc = 0
        for m in reg.enabled_ids():
            rc |= download_one(m, offline=False)
        return rc
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
