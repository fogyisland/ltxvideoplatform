# app/api/schemas.py
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    expires_in: int


class UserOut(BaseModel):
    id: int
    username: str
    role: str


class ModelOut(BaseModel):
    id: str
    display_name: str
    kind: str
    default_steps: int
    default_frames: int
    vram_gb: int
    enabled: bool
    description: str


class GenerateIn(BaseModel):
    model_id: str
    prompt: str
    negative_prompt: Optional[str] = None
    num_frames: int = Field(ge=9)
    height: int = Field(ge=64, multiple_of=32)
    width: int = Field(ge=64, multiple_of=32)
    num_inference_steps: int = Field(ge=1, le=200)
    guidance_scale: float = Field(ge=0.0, le=20.0)
    seed: Optional[int] = None
    fps: int = 24
    temporal_tile_size: Optional[int] = None
    temporal_overlap: Optional[int] = None
    image_upload_id: Optional[str] = None
    strength: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    frame_uploads: Optional[list[dict]] = None
    parent_job_id: Optional[str] = None
    extra_frames: Optional[int] = None
    two_stage: Optional[bool] = False
