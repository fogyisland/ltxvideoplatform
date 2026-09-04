# app/ui/api_client.py
from __future__ import annotations
import time
from typing import Any

import httpx


class ApiClient:
    def __init__(self, base_url: str, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._c = httpx.Client(base_url=self.base_url, timeout=httpx.Timeout(60.0, connect=10.0))

    def _h(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def login(self, username: str, password: str) -> str:
        r = self._c.post("/api/v1/auth/login",
                         data={"username": username, "password": password})
        r.raise_for_status()
        self.token = r.json()["access_token"]
        return self.token

    def me(self) -> dict:
        return self._c.get("/api/v1/auth/me", headers=self._h()).json()

    def list_models(self) -> list[dict]:
        return self._c.get("/api/v1/models", headers=self._h()).json()

    def upload(self, path: str) -> str:
        with open(path, "rb") as f:
            r = self._c.post("/api/v1/uploads",
                             files={"file": (path, f, "image/png")},
                             headers=self._h())
        r.raise_for_status()
        return r.json()["id"]

    def submit_t2v(self, **kw) -> str:
        r = self._c.post("/api/v1/t2v", json=kw, headers=self._h())
        r.raise_for_status(); return r.json()["job_id"]

    def submit_i2v(self, **kw) -> str:
        r = self._c.post("/api/v1/i2v", json=kw, headers=self._h())
        r.raise_for_status(); return r.json()["job_id"]

    def submit_extend(self, **kw) -> str:
        r = self._c.post("/api/v1/extend", json=kw, headers=self._h())
        r.raise_for_status(); return r.json()["job_id"]

    def get_job(self, job_id: str) -> dict:
        return self._c.get(f"/api/v1/jobs/{job_id}", headers=self._h()).json()

    def wait_job(self, job_id: str, timeout_sec: int = 1800, on_progress=None) -> dict:
        t0 = time.time()
        while True:
            j = self.get_job(job_id)
            if on_progress:
                on_progress(j)
            if j["status"] in ("succeeded", "failed", "cancelled"):
                return j
            if time.time() - t0 > timeout_sec:
                raise TimeoutError(job_id)
            time.sleep(1.0)

    def list_history(self, **kw) -> list[dict]:
        return self._c.get("/api/v1/history", params=kw, headers=self._h()).json()

    def result_url(self, job_id: str) -> str:
        return f"{self.base_url}/api/v1/jobs/{job_id}/result"
