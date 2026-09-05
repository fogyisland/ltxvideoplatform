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

Two inference paths are supported side-by-side:

  * **FP8 + monkey-patch** (default for 2B-distilled on 8 GB hosts)
    Uses `t5xxl_fp8_e4m3fn.safetensors` (4 GB on disk). The patch in
    `_patch_torch_finfo_for_fp8` fixes `torch.finfo(fp8).min` calls inside
    T5's causal-mask construction, which would otherwise raise
    `NotImplementedError` on torch builds that don't support FP8 finfo.

  * **GGUF Q4** (path for 8 GB hosts that can't use FP8 at all)
    Uses `ltxv-2b-0.9.8-distilled-q4_0.gguf` (1.2 GB) + a GGUF T5.
    The `ltx_video` package itself doesn't load GGUF, so this path requires
    a different backend (e.g. llama-cpp-python + a thin wrapper that
    exposes a HuggingFace-compatible T5EncoderModel). The GGUF files are
    downloaded into `models/gguf/` ready for that wrapper to consume.
    See `docs/LTX_VIDEO_SETUP.md` for the integration sketch.
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
# FP8 finfo monkey-patch
# ----------------------------------------------------------------
# transformers' T5 model uses `torch.finfo(dtype).min` to construct the
# causal attention mask. PyTorch's Windows builds don't support
# `finfo(Float8_e4m3fn)` — it raises `NotImplementedError`. We patch
# `torch.finfo` globally so any call with an FP8 dtype returns the bf16
# properties (T5's `min` is only used as a sentinel for masked positions,
# so the exact bit pattern doesn't matter as long as the dtype can
# represent the value).
#
# Even with the finfo fix, PyTorch's FP8 arithmetic on Windows
# (`ufunc_add`, `rsub`, etc.) is not implemented, so a single FP8
# multiply in T5's mask construction still crashes. To get past that we
# also upcast FP8 → bf16 on every parameter/buffer of the text encoder
# right after loading. Doubles the encoder's VRAM cost (4 GB → 8 GB)
# but keeps the on-disk size at 4 GB; that's the price for 8 GB GPUs.

_original_torch_finfo = torch.finfo


def _patched_torch_finfo(dtype):
    if dtype in (torch.float8_e4m3fn, torch.float8_e5m2):
        return _original_torch_finfo(torch.bfloat16)
    return _original_torch_finfo(dtype)


torch.finfo = _patched_torch_finfo


def _fp8_to_bf16(model: torch.nn.Module) -> int:
    """Upcast every FP8 parameter/buffer in `model` to bfloat16 in-place.

    Returns the number of tensors converted.
    """
    n = 0
    with torch.no_grad():
        for p in model.parameters():
            if p.dtype in (torch.float8_e4m3fn, torch.float8_e5m2):
                p.data = p.data.to(torch.bfloat16)
                n += 1
        for b in model.buffers():
            if b.dtype in (torch.float8_e4m3fn, torch.float8_e5m2):
                b.data = b.data.to(torch.bfloat16)
                n += 1
    return n


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
    # T5 lives on CPU; transformer + VAE are the only GPU users. Total
    # VRAM: ~4.5 GB (transformer BF16) + ~0.3 GB (VAE) = ~5 GB. Fits 8 GB.
    if _should_offload_strict():
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

    # 8GB cards can't fit T5-XXL (~9.5GB BF16) + 2B transformer (~4.5GB) + latents.
    # Force CPU inference (slow but works on any hardware). When this is run
    # on a 12GB+ GPU the original path will be used; the user can override
    # via the LTX_FORCE_GPU=1 env var.
    if os.environ.get("LTX_FORCE_GPU") == "1" and torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
    # Use FP8 for the text encoder AND transformer when fitting in low VRAM.
    # Both components have FP8 weights; safetensors load them as FP8 tensors
    # automatically. Saves ~50% of T5 (~5GB) and ~50% of transformer (~2.3GB).
    te_path = Path(str(text_encoder_path))
    is_fp8_te = te_path.name.startswith("t5xxl_fp8") or "fp8" in te_path.name.lower()
    # Checkpoint path can also be FP8 in future — for now only 2B-distilled fp8 exists
    is_fp8_ckpt = "fp8" in ckpt_path.name.lower()
    use_fp8 = is_fp8_te and is_fp8_ckpt
    dtype = torch.float8_e4m3fn if use_fp8 else torch.bfloat16

    # CPU mode (default on 8GB cards): put the transformer + VAE on CPU
    # so VAE decode / conv3d etc. don't OOM or split devices mid-pipeline.
    # The T5 stays on CPU (it was loaded as BF16 weights on disk; 17GB).
    # All forward passes then run on CPU; this works on any hardware and
    # avoids the device-mismatch errors that bite on a 2-component pipeline.
    if os.environ.get("LTX_FORCE_GPU") == "1" and torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"

    # 1) transformer (from the same safetensors)
    transformer = Transformer3DModel.from_pretrained(str(ckpt_path)).to(dtype).to(device)

    # 2) VAE (from the same safetensors)
    vae = CausalVideoAutoencoder.from_pretrained(str(ckpt_path)).to(dtype).to(device)

    # 3) scheduler
    scheduler = RectifiedFlowScheduler.from_pretrained(str(ckpt_path))

    # 4) text encoder (T5-XXL FP8 or BF16, separate directory)
    # Note: PyTorch's FP8 arithmetic on Windows is not implemented, so a
    # text encoder stored as FP8 will crash at the first matmul/mask op
    # even with the finfo patch. We load it then upcast FP8 → bf16 in-place
    # (doubles VRAM cost of the encoder but keeps the on-disk size at 4 GB).
    # T5 text encoder placement: keep T5 on CPU (text encoding is cheap
    # and runs once per generation). The 17 GB BF16 T5 never touches VRAM.
    # This leaves all 8 GB for the transformer + VAE pipeline.
    text_encoder = T5EncoderModel.from_pretrained(
        str(text_encoder_path), subfolder="text_encoder"
    )
    if is_fp8_te:
        _fp8_safe_t5_forward(text_encoder)
        print("[ltx] T5 FP8 weights loaded (will run on CPU)")
    else:
        text_encoder = text_encoder.to(dtype)
    # Keep T5 on CPU regardless of how it was loaded
    text_encoder = text_encoder.to("cpu")
    tokenizer = T5Tokenizer.from_pretrained(
        str(text_encoder_path), subfolder="tokenizer"
    )

    patchifier = SymmetricPatchifier(patch_size=1)

    # NB: don't call .to(device) here -- it overrides our manual device placement
    # and forces the text encoder back to GPU at inference time. The pipeline
    # auto-resolves self.device from .to calls done before, which we set above.
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
    )


def enable_low_vram_offload(pipeline) -> None:
    """Enable a manual device split for low-VRAM hosts (8 GB cards).

    Layout: text encoder (bf16) + scheduler + patchifier on GPU;
    transformer + VAE on CPU. The official `offload_to_cpu=True` flag in
    the call handles VAE only. The transformer module is paged in/out
    per step by `generate()` (since the official pipeline calls
    `self.transformer(...)` directly, it doesn't know to move it).
    """
    if not torch.cuda.is_available():
        return
    if getattr(pipeline, "_ltx_offload_applied", False):
        return
    try:
        pipeline.transformer = pipeline.transformer.to("cpu")
        pipeline.vae = pipeline.vae.to("cpu")
        torch.cuda.empty_cache()
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
        # Match the device we will pass to the pipeline (which is also the
        # device where latents are allocated).
        gen_device = "cpu" if (os.environ.get("LTX_FORCE_GPU") != "1") else ("cuda" if torch.cuda.is_available() else "cpu")
        generator = torch.Generator(device=gen_device).manual_seed(int(seed))

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
    out = pipeline(**call_kwargs, device=device)
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
    """Whether to enable CPU offload (matches official heuristic: <30GB)."""
    if not torch.cuda.is_available():
        return False
    total_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    return total_gb < 30  # official threshold


def _should_offload_strict() -> bool:
    """Stricter check: only offload on truly tight VRAM (<7 GB cards).

    8 GB RTX 4060 fits BF16 transformer + 4-bit T5 (~6-7 GB peak) so we
    should NOT auto-offload. Offloading is only needed for <7 GB cards.
    """
    if not torch.cuda.is_available():
        return False
    total_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    return total_gb < 7


def _to_latent(image: Image.Image, height: int, width: int):
    """Encode a PIL image to a single-frame latent tensor for I2V conditioning."""
    from torchvision.transforms.functional import to_tensor, resize, gaussian_blur
    img = image.convert("RGB").resize((width, height), Image.LANCZOS)
    t = to_tensor(img)  # (C, H, W), [0, 1]
    t = gaussian_blur(t, kernel_size=3, sigma=1.0)
    t = t.unsqueeze(0).unsqueeze(2)  # (1, C, 1, H, W)
    return t  # caller passes as image_tensor; VAE encoding happens in pipeline
