import pytest
from app.core.pipeline_manager import PipelineManager
from tests.fixtures.mock_pipeline import MockPipeline

def test_load_and_get(monkeypatch):
    pm = PipelineManager()
    pm.load("m1", loader=lambda _: MockPipeline("m1"))
    assert pm.current_id == "m1"
    assert pm.get().model_id == "m1"

def test_load_replaces(monkeypatch):
    pm = PipelineManager()
    pm.load("m1", loader=lambda _: MockPipeline("m1"))
    pm.load("m2", loader=lambda _: MockPipeline("m2"))
    assert pm.current_id == "m2"

def test_unload_clears():
    pm = PipelineManager()
    pm.load("m1", loader=lambda _: MockPipeline("m1"))
    pm.unload()
    assert pm.current_id is None
    assert pm.get() is None