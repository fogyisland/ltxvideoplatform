# tests/integration/test_api_models.py
"""Smoke test for the models listing endpoint.

Exercises the FastAPI app's ``GET /api/v1/models`` route against the
real ``models/registry.yaml`` shipped at the repo root. The endpoint
returns :class:`app.api.schemas.ModelOut` entries derived from the YAML
registry — it does not touch the DB ``models`` table, so this test is
independent of bootstrap ordering.
"""


def test_models_list_returns_200_and_canonical_ids(client, auth_headers):
    r = client.get("/api/v1/models", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    ids = {m["id"] for m in body}
    # The 2B distilled entry is the lightweight, low-VRAM model that the
    # brief mandates must be present.
    assert "ltx-2b-distilled" in ids
    # Spot-check a couple of other canonical IDs from registry.yaml.
    assert "ltx-13b-distilled" in ids


def test_models_list_requires_auth(client):
    r = client.get("/api/v1/models")
    assert r.status_code == 401


def test_models_list_entry_shape(client, auth_headers):
    r = client.get("/api/v1/models", headers=auth_headers)
    assert r.status_code == 200, r.text
    entry = next(m for m in r.json() if m["id"] == "ltx-2b-distilled")
    # Required fields per app.api.schemas.ModelOut.
    for key in ("id", "display_name", "kind", "default_steps",
                "default_frames", "vram_gb", "enabled", "description"):
        assert key in entry, f"missing field: {key}"