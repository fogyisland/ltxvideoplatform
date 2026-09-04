from __future__ import annotations
import io
from typing import Callable

from app.core.long_video import split_prompts, window_plan


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
    image: "PIL.Image.Image | None" = None,
    strength: float | None = None,
    frame_uploads: list | None = None,
    # Long-video
    temporal_tile_size: int | None = None,
    temporal_overlap: int | None = None,
) -> bytes:
    """Returns mp4 bytes. The actual LTXVideoPipeline signature must be verified
    against the installed LTX-Video version during implementation (Spec §14 R1).
    This wrapper absorbs any signature drift so callers stay stable."""
    on_step = on_step or (lambda s, t: None)

    common = dict(
        prompt=prompt,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
        height=height,
        width=width,
        num_frames=num_frames,
        seed=seed,
        fps=fps,
        callback_on_step_end=lambda _pipe, step, _t, _kwargs: on_step(step + 1, num_inference_steps),
    )

    if image is not None and strength is not None:
        common["image"] = image
        common["strength"] = strength

    if frame_uploads:
        common["keyframe_inputs"] = frame_uploads  # implementation verifies adapter name

    if temporal_tile_size and temporal_overlap and num_frames > temporal_tile_size:
        plan = window_plan(num_frames, temporal_tile_size, temporal_overlap)
        common["temporal_window_plan"] = plan
        common["prompt"] = split_prompts(prompt, len(plan))

    # Call the underlying pipeline; the result must be saved as mp4 bytes.
    out = pipeline(**common)
    return _frames_to_mp4_bytes(out, fps=fps)


def _frames_to_mp4_bytes(frames, fps: int) -> bytes:
    """Convert a list of PIL.Image (or numpy array) frames to MP4 bytes via imageio."""
    import imageio.v2 as imageio
    import numpy as np
    buf = io.BytesIO()
    writer = imageio.get_writer(buf, format="mp4", fps=fps, codec="libx264", quality=8)
    try:
        for f in frames:
            arr = np.asarray(f)
            if arr.ndim == 4 and arr.shape[0] == 1:
                arr = arr[0]
            writer.append_data(arr)
    finally:
        writer.close()
    return buf.getvalue()