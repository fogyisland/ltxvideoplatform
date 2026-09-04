from pathlib import Path

from app.storage import files


def test_resolve_is_user_isolated():
    p = files.resolve(7, "uploads", "abc.png")
    assert p == Path("./data/uploads/7/abc.png").resolve()


def test_verify_owner_allows_own_path(tmp_path):
    p = tmp_path / "uploads" / "3" / "x.png"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"x")
    assert files.verify_owner(p, 3) is True


def test_verify_owner_rejects_other_user(tmp_path):
    p = tmp_path / "uploads" / "3" / "x.png"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"x")
    assert files.verify_owner(p, 4) is False


def test_save_upload_writes_and_hashes(tmp_path, monkeypatch):
    monkeypatch.setattr(files, "uploads_dir", tmp_path / "uploads")
    path, sha = files.save_upload(9, b"hello", ".png")
    assert path.exists()
    assert path.read_bytes() == b"hello"
    assert len(sha) == 64  # sha256 hex
