from app.core.long_video import split_prompts, window_plan

def test_split_prompts_pads():
    out = split_prompts("a | b | c", num_windows=5)
    assert out == ["a", "b", "c", "c", "c"]

def test_split_prompts_single():
    assert split_prompts("only one", 3) == ["only one"] * 3

def test_window_plan_basic():
    plan = window_plan(num_frames=161, tile_size=80, overlap=24)
    # each window 80 frames; advance by 80-24=56
    assert plan[0] == (0, 80)
    assert plan[1] == (56, 136)
    assert plan[2] == (112, 161)  # last clips at end