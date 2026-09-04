from __future__ import annotations


def split_prompts(prompt: str, num_windows: int) -> list[str]:
    parts = [p.strip() for p in prompt.split("|") if p.strip()]
    if not parts:
        parts = [""]
    if len(parts) >= num_windows:
        return parts[:num_windows]
    # pad with the last segment
    return parts + [parts[-1]] * (num_windows - len(parts))


def window_plan(num_frames: int, tile_size: int, overlap: int) -> list[tuple[int, int]]:
    if tile_size <= overlap:
        raise ValueError("tile_size must be greater than overlap")
    step = tile_size - overlap
    plan: list[tuple[int, int]] = []
    start = 0
    while start < num_frames:
        end = min(start + tile_size, num_frames)
        plan.append((start, end))
        if end == num_frames:
            break
        start += step
    return plan