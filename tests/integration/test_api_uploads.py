# tests/integration/test_api_uploads.py
def test_upload_then_list(client, auth_headers):
    r = client.post("/api/v1/uploads",
                    files={"file": ("a.png", b"\x89PNG\r\n\x1a\n", "image/png")},
                    headers=auth_headers)
    assert r.status_code == 200, r.text
    assert "id" in r.json()
