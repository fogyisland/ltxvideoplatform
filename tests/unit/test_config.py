import pytest
from pathlib import Path

def test_settings_loads_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVICE", "cuda")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-pw")
    from app.config import get_settings
    get_settings.cache_clear()
    s = get_settings()
    assert s.device == "cuda"
    assert isinstance(s.data_dir_abs, Path)
    assert s.uploads_dir == s.data_dir_abs / "uploads"
    assert s.outputs_dir == s.data_dir_abs / "outputs"
    assert s.jwt_expires_min == 720
