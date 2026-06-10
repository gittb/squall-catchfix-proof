from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_create_and_get_note() -> None:
    nid = client.post("/notes", json={"body": "hello"}).json()["id"]
    assert client.get(f"/notes/{nid}").json() == {"body": "hello"}


# --- export / import (catch-and-fix revision) ---


def test_export_import_roundtrip() -> None:
    nid = client.post("/notes", json={"body": "round-trip body"}).json()["id"]
    # Export the note to the sandbox.
    r = client.post("/notes/export", json={"note_id": nid})
    assert r.status_code == 200, r.text
    # The response names a file inside the sandbox.
    written = r.json()["written"]
    assert written == f"note_{nid}.txt"
    # Import it back and confirm the body matches.
    r2 = client.get("/notes/import", params={"path": written})
    assert r2.status_code == 200, r2.text
    assert r2.json() == {"body": "round-trip body"}


def test_export_empty_store_returns_404() -> None:
    # No notes created — the export endpoint must return 404, not
    # KeyError/500.
    r = client.post("/notes/export", json={"note_id": 1})
    assert r.status_code == 404
    assert "detail" in r.json()


def test_export_unknown_note_id_returns_404() -> None:
    # Store is non-empty (we just created one) but the requested id is
    # bogus — still 404.
    client.post("/notes", json={"body": "exists"})
    r = client.post("/notes/export", json={"note_id": 9999})
    assert r.status_code == 404


def test_import_traversal_rejected() -> None:
    # Classic traversal: ../../etc/passwd must be rejected with 4xx.
    r = client.get("/notes/import", params={"path": "../../etc/passwd"})
    assert 400 <= r.status_code < 500, r.text


def test_import_absolute_path_rejected() -> None:
    # Absolute paths pointing elsewhere must be rejected.
    r = client.get("/notes/import", params={"path": "/etc/hostname"})
    assert 400 <= r.status_code < 500, r.text


def test_import_separator_rejected() -> None:
    # Even a single separator should be rejected.
    r = client.get("/notes/import", params={"path": "subdir/file.txt"})
    assert 400 <= r.status_code < 500, r.text


def test_import_nonexistent_file_returns_404() -> None:
    # Valid basename, but no such file in the sandbox → 404.
    r = client.get("/notes/import", params={"path": "does_not_exist.txt"})
    assert r.status_code == 404
