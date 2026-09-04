# tests/unit/test_registry.py
from pathlib import Path
from app.core.registry import Registry, load

def test_load_registry(tmp_path: Path):
    yaml = tmp_path / "reg.yaml"
    yaml.write_text("""
models:
  - id: ltx-2b-distilled
    display_name: "LTX-Video 2B Distilled"
    kind: t2v_distilled
    checkpoint_path: ltx-video-2b-distilled/model.safetensors
    config_path: ltx-video-2b-distilled/config.yaml
    default_steps: 8
    default_frames: 97
    vram_gb: 6
    enabled: true
    description: tiny
""")
    reg = load(yaml)
    assert isinstance(reg, Registry)
    e = reg.by_id("ltx-2b-distilled")
    assert e is not None
    assert e.default_steps == 8
    assert e.vram_gb == 6
