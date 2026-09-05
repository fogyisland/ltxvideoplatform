#!/usr/bin/env python3
"""Download GGUF-quantized LTX-Video 2B-distilled + T5-XXL from calcuis/ltxv-gguf.

Used by the optional llama-cpp-python inference path (8 GB GPUs). The official
`ltx_video` package doesn't load GGUF, so these files are dormant until a
wrapper is added that exposes a HuggingFace-compatible T5 encoder from a
GGUF via llama-cpp.

Quantizations downloaded:
  - 2B distilled Q4_0:  1.2 GB (transformer)
  - T5-XXL    Q4_0:  2.7 GB (text encoder)
  Total: ~4 GB on disk, ~3.5-4 GB VRAM at load.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parent.parent
GGUF_DIR = ROOT / "models" / "gguf"

FILES = [
    ("calcuis/ltxv-gguf", "ltxv-2b-0.9.8-distilled-q4_0.gguf", GGUF_DIR),
    ("calcuis/ltxv-gguf", "t5xxl_fp16-q4_0.gguf", GGUF_DIR / "t5xxl_q4_0"),
]


def main() -> int:
    for repo, fn, sub in FILES:
        sub.mkdir(parents=True, exist_ok=True)
        p = hf_hub_download(repo_id=repo, filename=fn, local_dir=str(sub))
        print(f"ok: {p}  ({Path(p).stat().st_size // (1024**3)} GB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
