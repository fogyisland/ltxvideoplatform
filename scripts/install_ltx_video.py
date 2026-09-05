#!/usr/bin/env python3
"""Install the ltx_video Python package from a local clone of
github.com/Lightricks/LTX-Video.

Why this script: the ltx_video package is not on PyPI. The official repo must
be cloned and `pip install -e .` run from inside it. If the local clone at
/tmp/LTX-Video does not exist, this script first attempts ghfast.top (a Chinese
GitHub mirror that usually works when raw github.com is blocked).

Usage:
    python scripts/install_ltx_video.py
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path("/tmp/LTX-Video")
REPO_URL = "https://github.com/Lightricks/LTX-Video.git"
MIRROR_URL = "https://ghfast.top/https://github.com/Lightricks/LTX-Video.git"


def main() -> int:
    if not REPO_DIR.exists():
        print(f"cloning to {REPO_DIR} (via {MIRROR_URL})…", flush=True)
        r = subprocess.run(["git", "clone", "--depth=1", MIRROR_URL, str(REPO_DIR)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print("mirror failed; trying raw github.com", flush=True)
            r = subprocess.run(["git", "clone", "--depth=1", REPO_URL, str(REPO_DIR)],
                               capture_output=True, text=True)
        if r.returncode != 0:
            print("clone failed:\n", r.stderr, file=sys.stderr)
            return 1
    print("installing (editable, no-deps)…", flush=True)
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(REPO_DIR), "--no-deps"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print("install failed:\n", r.stderr, file=sys.stderr)
        return 1
    print("done. ltx_video is now importable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())