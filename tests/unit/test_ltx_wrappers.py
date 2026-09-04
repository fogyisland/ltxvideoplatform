from tests.fixtures.mock_pipeline import MockPipeline
from app.core.ltx_wrappers import generate

def test_generate_returns_mp4_bytes():
    p = MockPipeline()
    out = generate(
        pipeline=p, kind="t2v", prompt="x", num_frames=9, height=32, width=32,
        num_inference_steps=2, guidance_scale=5.0, seed=0, fps=8,
    )
    assert isinstance(out, bytes)
    assert len(out) > 0
    assert p.calls, "pipeline was not invoked"

def test_long_video_passes_window_plan_and_split_prompts():
    p = MockPipeline()
    generate(
        pipeline=p, kind="t2v", prompt="a | b | c",
        num_frames=161, height=32, width=32,
        num_inference_steps=2, guidance_scale=5.0, seed=0, fps=8,
        temporal_tile_size=80, temporal_overlap=24,
    )
    args = p.calls[0]
    assert isinstance(args["temporal_window_plan"], list)
    assert len(args["prompt"]) == 3  # 161 frames / 56 step = 3 windows