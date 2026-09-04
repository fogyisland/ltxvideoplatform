# tests/integration/test_api_generation.py
def test_t2v_enqueues(client, auth_headers, monkeypatch):
    # Stub the queue so we don't actually run inference
    from app.core import job_queue as jq
    called = {}
    def fake_submit(*, kind, user_id, model_id, params, parent_job_id=None):
        called["kind"] = kind; called["model_id"] = model_id
        return "01HFAKE0000000000000000000"
    monkeypatch.setattr(jq.get_queue(), "submit", fake_submit)
    r = client.post("/api/v1/t2v", json={
        "model_id": "ltx-2b-distilled", "prompt": "x", "num_frames": 9,
        "height": 64, "width": 64, "num_inference_steps": 2, "guidance_scale": 5.0,
    }, headers=auth_headers)
    assert r.status_code == 202
    assert called["kind"] == "t2v"
