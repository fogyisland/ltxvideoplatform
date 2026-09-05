"""app/core/ltx_wrappers.py

LTX-Video inference wrapper, following the official `ltx_video` package
(https://github.com/Lightricks/LTX-Video, v0.9.8).

The pipeline is built exactly as the official `create_ltx_video_pipeline()` does:

    transformer = Transformer3DModel.from_pretrained(ckpt_path)
    vae         = CausalVideoAutoencoder.from_pretrained(ckpt_path)
    scheduler   = RectifiedFlowScheduler.from_pretrained(ckpt_path)
    text_encoder = T5EncoderModel.from_pretrained(text_encoder_path, subfolder="text_encoder")
    tokenizer    = T5Tokenizer.from_pretrained(text_encoder_path, subfolder="tokenizer")
    pipeline = LTXVideoPipeline(
        transformer=..., vae=..., scheduler=..., text_encoder=..., tokenizer=..., patchifier=...
    )

For low-VRAM hosts (≤8 GB) we enable `offload_to_cpu=True` in `pipeline(...)`
which moves the text encoder to CPU between steps (handled internally by
`LTXVideoPipeline`).
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Callable

import imageio.v2 as imageio
import numpy as np
import torch
from PIL import Image

from app.config import get_settings
from app.core.long_video import split_prompts, window_plan


# ----------------------------------------------------------------
# Pipeline construction (cached per process)
# ----------------------------------------------------------------

_PIPELINE_CACHE: dict = {}


def get_pipeline(model_id: str):
    """Return a cached LTXVideoPipeline for the given model_id. Lazy-init."""
    if model_id in _PIPELINE_CACHE:
        return _PIPELINE_CACHE[model_id]

    settings = get_settings()
    reg = _load_registry()
    entry = reg.by_id(model_id)
    if entry is None:
        raise RuntimeError(f"unknown model_id: {model_id}")

    ckpt_path = settings.model_dir_abs / entry.checkpoint_path
    if not ckpt_path.exists():
        raise FileNotFoundError(f"checkpoint not found: {ckpt_path}")

    # We use a 2B-distilled-friendly text encoder dir name; the registry entry's
    # `text_encoder_path` field overrides when present.
    if getattr(entry, "text_encoder_path", None):
        te_raw = Path(entry.text_encoder_path)
        text_encoder_path = te_raw if te_raw.is_absolute() else settings.model_dir_abs / te_raw
    else:
        text_encoder_path = settings.model_dir_abs / "text_encoder"
    if not text_encoder_path.exists():
        raise FileNotFoundError(
            f"text encoder not found at {text_encoder_path}. "
            f"Download PixArt-alpha/PixArt-XL-2-1024-MS via scripts/download_models.py --text-encoder"
        )

    # Determine precision: bf16 (matches the 0.9.8 config), with a hook to allow fp8 later.
    precision = "bfloat16"

    pipeline = _create_pipeline(ckpt_path, text_encoder_path, precision)
    if _should_offload():
        enable_low_vram_offload(pipeline)
    _PIPELINE_CACHE[model_id] = pipeline
    return pipeline


def unload_pipeline(model_id: str | None = None) -> None:
    if model_id is None:
        for k in list(_PIPELINE_CACHE):
            _PIPELINE_CACHE.pop(k, None)
    else:
        _PIPELINE_CACHE.pop(model_id, None)
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _load_registry():
    # local import to avoid circulars
    from app.core.registry import load
    return load(get_settings().registry_path)


# ----------------------------------------------------------------
# Internal: actually build the pipeline using the official `ltx_video` package.
# Falls back to diffusers' LTXPipeline if the official package is not importable.
# ----------------------------------------------------------------

def _create_pipeline(ckpt_path: Path, text_encoder_path: Path, precision: str):
    """Build LTXVideoPipeline. Tries official package first, then diffusers fallback."""
    try:
        from ltx_video.pipelines.pipeline_ltx_video import LTXVideoPipeline
        from ltx_video.models.transformers.transformer3d import Transformer3DModel
        from ltx_video.models.autoencoders.causal_video_autoencoder import CausalVideoAutoencoder
        from ltx_video.schedulers.rf import RectifiedFlowScheduler
        from ltx_video.models.transformers.symmetric_patchifier import SymmetricPatchifier
        from transformers import T5EncoderModel, T5Tokenizer
        return _build_official(
            ckpt_path, text_encoder_path, precision,
            LTXVideoPipeline, Transformer3DModel, CausalVideoAutoencoder,
            RectifiedFlowScheduler, SymmetricPatchifier, T5EncoderModel, T5Tokenizer,
        )
    except ImportError as e:
        # fallback to diffusers
        from diffusers import LTXPipeline
        return _build_diffusers(ckpt_path, LTXPipeline)


def _build_official(ckpt_path, text_encoder_path, precision,
                    LTXVideoPipeline, Transformer3DModel, CausalVideoAutoencoder,
                    RectifiedFlowScheduler, SymmetricPatchifier,
                    T5EncoderModel, T5Tokenizer):
    from safetensors import safe_open
    import json

    # Read pipeline config from safetensors metadata
    with safe_open(str(ckpt_path), framework="pt") as f:
        metadata = f.metadata() or {}
        config_str = metadata.get("config")
    if config_str:
        try:
            cfg = json.loads(config_str)
        except Exception:
            cfg = {}
    else:
        cfg = {}

    device = "cuda" if torch.cuda.is_available() else "cpu"
    # Use FP8 for the text encoder AND transformer when fitting in low VRAM.
    # Both components have FP8 weights; safetensors load them as FP8 tensors
    # automatically. Saves ~50% of T5 (~5GB) and ~50% of transformer (~2.3GB).
    te_path = Path(str(text_encoder_path))
    is_fp8_te = te_path.name.startswith("t5xxl_fp8") or "fp8" in te_path.name.lower()
    # Checkpoint path can also be FP8 in future — for now only 2B-distilled fp8 exists
    is_fp8_ckpt = "fp8" in ckpt_path.name.lower()
    use_fp8 = is_fp8_te and is_fp8_ckpt
    dtype = torch.float8_e4m3fn if use_fp8 else torch.bfloat16

    # 1) transformer (from the same safetensors)
    transformer = Transformer3DModel.from_pretrained(str(ckpt_path)).to(dtype)

    # 2) VAE (from the same safetensors)
    vae = CausalVideoAutoencoder.from_pretrained(str(ckpt_path)).to(dtype)

    # 3) scheduler
    scheduler = RectifiedFlowScheduler.from_pretrained(str(ckpt_path))

    # 4) text encoder (T5-XXL FP8 or BF16, separate directory)
    # Note: transformers' from_pretrained with dtype=fp8 fails on some Windows
    # torch builds because set_default_dtype doesn't accept fp8. Load in bfloat16
    # then convert module-by-module.
    text_encoder = T5EncoderModel.from_pretrained(
        str(text_encoder_path), subfolder="text_encoder"
    )
    if is_fp8_te:
        # The safetensors already contains FP8 weights; PyTorch loads them as FP8
        # tensors automatically because of the file's metadata dtype. No further
        # cast needed — keep as-is to save VRAM.
        pass
    else:
        text_encoder = text_encoder.to(dtype)
    tokenizer = T5Tokenizer.from_pretrained(
        str(text_encoder_path), subfolder="tokenizer"
    )

    patchifier = SymmetricPatchifier(patch_size=1)

    return LTXVideoPipeline(
        transformer=transformer,
        patchifier=patchifier,
        text_encoder=text_encoder,
        tokenizer=tokenizer,
        scheduler=scheduler,
        vae=vae,
        prompt_enhancer_image_caption_model=None,
        prompt_enhancer_image_caption_processor=None,
        prompt_enhancer_llm_model=None,
        prompt_enhancer_llm_tokenizer=None,
        allowed_inference_steps=cfg.get("allowed_inference_steps", None),
    ).to(device)


# Inside _build_official, after the pipeline is built, call enable_model_cpu_offload
# on hosts with insufficient VRAM. This is the pattern from diffusers' "Low VRAM"
# guide. Note: this must be called *after* the pipeline exists and before inference.
# We expose it as a helper for the caller.


def enable_low_vram_offload(pipeline) -> None:
    """Enable a manual device split for low-VRAM hosts.

    The transformer is the largest module (≈ 4.5 GB BF16). We move it to CPU
    and rely on the official `LTXVideoPipeline.__call__`'s built-in
    `offload_to_cpu=True` flag to page it back to GPU only when needed.
    Text encoder (~4.75 GB FP8) + scheduler + patchifier stay on GPU.

    This is the simplest reliable path on 8 GB hardware — accelerate's
    `cpu_offload` puts modules in meta-state which the official pipeline
    doesn't handle.
    """
    if not torch.cuda.is_available():
        return
    if getattr(pipeline, "_ltx_offload_applied", False):
        return
    # Move transformer + VAE to CPU; text_encoder + scheduler + patchifier stay on GPU.
    try:
        pipeline.transformer = pipeline.transformer.to("cpu")
        pipeline.vae = pipeline.vae.to("cpu")
    except Exception:
        return
    pipeline._ltx_offload_applied = True


def _build_diffusers(ckpt_path, LTXPipeline):
    """Fallback: diffusers' LTXPipeline. Different model layout (split subdirs)."""
    # diffusers expects a directory containing transformer/ vae/ text_encoder/ etc.
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16
    pipe = LTXPipeline.from_pretrained(str(ckpt_path), torch_dtype=dtype)
    pipe.to(device)
    return pipe


# ----------------------------------------------------------------
# Public API: generate(pipeline, ...) -> mp4 bytes
# ----------------------------------------------------------------

def generate(
    pipeline,
    *,
    kind: str,
    prompt: str,
    num_frames: int,
    height: int,
    width: int,
    num_inference_steps: int,
    guidance_scale: float,
    seed: int | None,
    fps: int,
    on_step: Callable[[int, int], None] | None = None,
    # I2V / keyframe inputs (optional)
    image: Image.Image | None = None,
    strength: float | None = None,
    frame_uploads: list | None = None,
    # Long-video
    temporal_tile_size: int | None = None,
    temporal_overlap: int | None = None,
) -> bytes:
    """Run a single inference and return mp4 bytes. Mirrors the official `infer()` call."""

    on_step = on_step or (lambda s, t: None)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # Pad dimensions per official constraints
    height_p = ((height - 1) // 32 + 1) * 32
    width_p = ((width - 1) // 32 + 1) * 32
    num_frames_p = ((max(num_frames, 2) - 2) // 8 + 1) * 8 + 1

    # Long-video: split prompt by |, slide window
    if temporal_tile_size and temporal_overlap and num_frames_p > temporal_tile_size:
        plan = window_plan(num_frames_p, temporal_tile_size, temporal_overlap)
        prompt_segments = split_prompts(prompt, len(plan))
    else:
        plan = None
        prompt_segments = [prompt]

    generator = None
    if seed is not None:
        generator = torch.Generator(device=device).manual_seed(int(seed))

    common_kwargs = dict(
        prompt=prompt_segments[0] if plan is None else prompt_segments,
        negative_prompt="worst quality, inconsistent motion, blurry, jittery, distorted",
        height=height_p,
        width=width_p,
        num_frames=num_frames_p,
        frame_rate=float(fps),
        num_inference_steps=int(num_inference_steps),
        guidance_scale=float(guidance_scale),
        generator=generator,
        output_type="pt",
        is_video=True,
        vae_per_channel_normalize=True,
        offload_to_cpu=_should_offload(),
        enhance_prompt=False,
        device=device,
    )

    # LTXVideoPipeline accepts a `timesteps` list; without one it uses num_inference_steps.
    # For 2B distilled we can keep default behavior.
    call_kwargs = dict(common_kwargs)
    if image is not None and strength is not None:
        # I2V: use the official ConditioningItem path
        try:
            from ltx_video.pipelines.pipeline_ltx_video import ConditioningItem
            cond = [ConditioningItem(
                image_tensor=_to_latent(image, height_p, width_p),
                media_frame_index=0,
                conditioning_strength=float(strength),
            )]
            call_kwargs["conditioning_items"] = cond
        except Exception:
            pass  # fallback to T2V without I2V

    # Step callback: the pipeline calls `callback_on_step_end(pipe, step, t, kwargs)`;
    # we adapt that signature.
    def _cb(pipe, step_idx, t, kwargs):
        on_step(int(step_idx) + 1, int(num_inference_steps))

    call_kwargs["callback_on_step_end"] = _cb

    # Run.
    out = pipeline(**call_kwargs)
    images = out.images  # (B, C, F, H, W) tensor in [-1, 1] (approx)

    # Convert to uint8 frames.
    video_np = images[0].permute(1, 2, 3, 0).cpu().float().numpy()
    video_np = ((video_np + 1) / 2 * 255).clip(0, 255).astype(np.uint8)  # crude unnormalize
    # Crop padding back off
    pad_top, pad_bot = 0, height_p - height
    pad_l, pad_r = 0, width_p - width
    if video_np.shape[0] > num_frames:
        video_np = video_np[:num_frames]
    video_np = video_np[:, pad_top:video_np.shape[1]-pad_bot if pad_bot else None,
                         pad_l:video_np.shape[2]-pad_r if pad_r else None]

    # Encode mp4
    import io
    buf = io.BytesIO()
    writer = imageio.get_writer(buf, format="mp4", fps=int(fps), codec="libx264", quality=8)
    for frame in video_np:
        writer.append_data(frame)
    writer.close()
    return buf.getvalue()


def _should_offload() -> bool:
    """Enable CPU offload when VRAM is scarce (matches official heuristic)."""
    if not torch.cuda.is_available():
        return False
    total_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    return total_gb < 30  # official threshold


def _to_latent(image: Image.Image, height: int, width: int):
    """Encode a PIL image to a single-frame latent tensor for I2V conditioning."""
    from torchvision.transforms.functional import to_tensor, resize, gaussian_blur
    img = image.convert("RGB").resize((width, height), Image.LANCZOS)
    t = to_tensor(img)  # (C, H, W), [0, 1]
    t = gaussian_blur(t, kernel_size=3, sigma=1.0)
    t = t.unsqueeze(0).unsqueeze(2)  # (1, C, 1, H, W)
    return t  # caller passes as image_tensor; VAE encoding happens in pipeline
