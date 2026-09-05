# app/core/registry.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass(frozen=True)
class ModelEntry:
    id: str
    display_name: str
    kind: str
    checkpoint_path: str
    config_path: str
    default_steps: int
    default_frames: int
    vram_gb: int
    enabled: bool
    description: str
    use_case: str = ""        # e.g. "fast previews", "high quality"
    disk_size_gb: float = 0.0  # approx on-disk size after snapshot_download
    text_encoder_path: str | None = None  # override default MODEL_DIR/text_encoder


@dataclass
class Registry:
    models: list[ModelEntry]

    def by_id(self, model_id: str) -> ModelEntry | None:
        for m in self.models:
            if m.id == model_id:
                return m
        return None

    def enabled_ids(self) -> list[str]:
        return [m.id for m in self.models if m.enabled]


def load(path: Path) -> Registry:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = [
        ModelEntry(
            id=m["id"],
            display_name=m["display_name"],
            kind=m["kind"],
            checkpoint_path=m["checkpoint_path"],
            config_path=m["config_path"],
            default_steps=int(m.get("default_steps", 20)),
            default_frames=int(m.get("default_frames", 121)),
            vram_gb=int(m.get("vram_gb", 16)),
            enabled=bool(m.get("enabled", True)),
            description=m.get("description", ""),
            use_case=m.get("use_case", ""),
            disk_size_gb=float(m.get("disk_size_gb", 0.0)),
            text_encoder_path=m.get("text_encoder_path") or None,
        )
        for m in raw["models"]
    ]
    return Registry(models=entries)


def to_db_rows(reg: Registry) -> list[dict]:
    return [m.__dict__ for m in reg.models]
