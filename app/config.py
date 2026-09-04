# app/config.py
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    app_host: str = "0.0.0.0"
    app_port_api: int = 8000
    app_port_gradio: int = 7860

    device: Literal["cuda"] = "cuda"  # only "cuda" in MVP

    data_dir: Path = Path("./data")
    model_dir: Path = Path("./models")
    registry_path: Path = Path("./models/registry.yaml")
    database_url: str = "sqlite:///./data/app.db"

    jwt_secret: str = Field(min_length=32)
    jwt_expires_min: int = 720
    admin_username: str = "admin"
    admin_password: str = "change-me"

    max_concurrent_jobs: int = 1
    job_timeout_sec: int = 1800
    output_disk_min_free_gb: int = 5

    log_level: str = "INFO"
    hf_token: str = ""
    gradio_auth_basic: str = ""  # "user:pass" fallback for Gradio UI

    @computed_field  # type: ignore[misc]
    @property
    def data_dir_abs(self) -> Path:
        return self.data_dir.resolve()

    @computed_field  # type: ignore[misc]
    @property
    def model_dir_abs(self) -> Path:
        return self.model_dir.resolve()

    @computed_field  # type: ignore[misc]
    @property
    def uploads_dir(self) -> Path:
        return self.data_dir_abs / "uploads"

    @computed_field  # type: ignore[misc]
    @property
    def outputs_dir(self) -> Path:
        return self.data_dir_abs / "outputs"

    @computed_field  # type: ignore[misc]
    @property
    def previews_dir(self) -> Path:
        return self.data_dir_abs / "previews"

    @computed_field  # type: ignore[misc]
    @property
    def db_path(self) -> Path:
        return self.data_dir_abs / "app.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
