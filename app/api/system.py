"""app/api/system.py

System info endpoint for the frontend: GPU detection, recommended inference
mode (cpu / gpu), and rough ETA hints per mode.
"""
from __future__ import annotations

import torch

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/system", tags=["system"])


# 16 GB is the soft floor for the official BF16 LTX-Video 2B path (text
# encoder 9.5 GB + transformer 4.5 GB + VAE 0.3 GB + latents).
VRAM_THRESHOLD_GB = 16.0


class SystemInfo(BaseModel):
    gpu_available: bool
    gpu_name: str | None
    vram_total_gb: float
    vram_used_gb: float
    recommended_mode: str  # "cpu" or "gpu"
    estimated_seconds_per_clip: int  # rough heuristic
    vram_threshold_gb: float = VRAM_THRESHOLD_GB


def _detect() -> SystemInfo:
    if not torch.cuda.is_available():
        return SystemInfo(
            gpu_available=False,
            gpu_name=None,
            vram_total_gb=0.0,
            vram_used_gb=0.0,
            recommended_mode="cpu",
            estimated_seconds_per_clip=30,
        )
    props = torch.cuda.get_device_properties(0)
    total = props.total_memory / (1024 ** 3)
    used = torch.cuda.memory_allocated() / (1024 ** 3)
    if total >= VRAM_THRESHOLD_GB:
        mode = "gpu"
        # 9-frame 256x256 4-step on RTX 4070-ish is ~5-8s
        eta = 6
    else:
        mode = "cpu"
        # CPU path: ~30-35s on RTX 4060
        eta = 33
    return SystemInfo(
        gpu_available=True,
        gpu_name=props.name,
        vram_total_gb=round(total, 2),
        vram_used_gb=round(used, 2),
        recommended_mode=mode,
        estimated_seconds_per_clip=eta,
    )


@router.get("/info", response_model=SystemInfo)
def system_info() -> SystemInfo:
    return _detect()
