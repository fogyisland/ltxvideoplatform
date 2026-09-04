# tests/e2e/test_gradio_login.py
from gradio_client import Client
import pytest


@pytest.mark.gpu(False)  # UI smoke only
def test_gradio_login_screen_loads(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("ADMIN_PASSWORD", "admin")
    from app.config import get_settings
    get_settings.cache_clear()
    from app.main import build_gradio_app
    blocks, _port = build_gradio_app(launch=False)
    # gradio_client requires running server; here we assert blocks build without error
    assert blocks is not None
