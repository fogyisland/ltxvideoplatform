from __future__ import annotations
import threading
from typing import Any

from app.config import get_settings


class PipelineManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pipeline: Any = None
        self._current_id: str | None = None

    @property
    def current_id(self) -> str | None:
        return self._current_id

    def load(self, model_id: str, loader=None) -> None:
        """`loader(model_id) -> pipeline` injected for testability."""
        with self._lock:
            if self._current_id == model_id and self._pipeline is not None:
                return
            new_pipeline = loader(model_id) if loader else self._default_loader(model_id)
            old = self._pipeline
            self._pipeline = new_pipeline
            self._current_id = model_id
            del old
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

    def unload(self) -> None:
        with self._lock:
            self._pipeline = None
            self._current_id = None
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

    def get(self) -> Any:
        return self._pipeline

    def status(self) -> dict:
        vram_used = vram_total = 0.0
        try:
            import torch
            if torch.cuda.is_available():
                free, total = torch.cuda.mem_get_info()
                vram_total = total / (1024 ** 3)
                vram_used = (total - free) / (1024 ** 3)
        except Exception:
            pass
        return {"current_id": self._current_id, "vram_used_gb": round(vram_used, 2),
                "vram_total_gb": round(vram_total, 2)}

    def _default_loader(self, model_id: str) -> Any:
        # Implemented in Task 6 wiring; placeholder kept here so unit tests work standalone.
        raise NotImplementedError("wire LTXVideoPipeline.from_pretrained in Task 6")


_singleton: PipelineManager | None = None


def get_manager() -> PipelineManager:
    global _singleton
    if _singleton is None:
        _singleton = PipelineManager()
    return _singleton