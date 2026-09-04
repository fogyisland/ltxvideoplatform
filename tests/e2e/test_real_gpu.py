# tests/e2e/test_real_gpu.py
import time
import pytest
import requests

pytestmark = pytest.mark.gpu


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    import subprocess, os, signal
    import sys
    tmp = tmp_path_factory.mktemp("gpu")
    env = os.environ.copy()
    env.update({
        "DATA_DIR": str(tmp / "data"),
        "MODEL_DIR": str(tmp / "models"),
        "JWT_SECRET": "x" * 32,
        "ADMIN_PASSWORD": "admin",
    })
    p = subprocess.Popen([sys.executable, "-m", "app.main"], env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    # wait for /healthz
    for _ in range(60):
        try:
            r = requests.get("http://127.0.0.1:8000/api/v1/models", timeout=1)
            if r.status_code in (401, 200):
                break
        except Exception:
            time.sleep(1)
    yield p
    p.send_signal(signal.SIGTERM)
    p.wait(timeout=10)


def test_real_t2v_2b(server):
    # login
    tok = requests.post("http://127.0.0.1:8000/api/v1/auth/login",
                        data={"username": "admin", "password": "admin"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    # 2B distilled with minimal settings — assumes checkpoint exists
    r = requests.post("http://127.0.0.1:8000/api/v1/t2v", json={
        "model_id": "ltx-2b-distilled",
        "prompt": "a red cube",
        "num_frames": 9,
        "height": 128, "width": 128,
        "num_inference_steps": 2,
        "guidance_scale": 5.0,
    }, headers=h)
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    # poll
    for _ in range(120):
        j = requests.get(f"http://127.0.0.1:8000/api/v1/jobs/{job_id}", headers=h).json()
        if j["status"] in ("succeeded", "failed"):
            break
        time.sleep(2)
    assert j["status"] == "succeeded", j.get("error")
    # fetch result
    r = requests.get(f"http://127.0.0.1:8000/api/v1/jobs/{job_id}/result", headers=h, stream=True)
    assert r.status_code == 200
    assert int(r.headers.get("content-length", 0)) > 1000