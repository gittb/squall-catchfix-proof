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


# --- GET /notes/{note_id}/html (XSS-safe rendered page) ---


def test_get_note_html_returns_html_page() -> None:
    nid = client.post("/notes", json={"body": "hello world"}).json()["id"]
    r = client.get(f"/notes/{nid}/html")
    assert r.status_code == 200, r.text
    # Content-Type must be text/html (not JSON).
    assert r.headers["content-type"].startswith("text/html"), r.headers
    body = r.text
    # Page is a complete, self-contained HTML document.
    assert "<!doctype html>" in body.lower()
    assert "<html" in body
    assert "<h1>Note #" + str(nid) + "</h1>" in body
    # Body content is present (escaped form is fine; this body has no markup).
    assert "hello world" in body


def test_get_note_html_unknown_id_returns_404() -> None:
    # No note with this id exists — must return 404 with an HTML body,
    # not the JSON shape that HTTPException produces.
    r = client.get("/notes/9999/html")
    assert r.status_code == 404, r.text
    assert r.headers["content-type"].startswith("text/html"), r.headers
    body = r.text
    assert "<!doctype html>" in body.lower()
    # The 404 page must NOT be a JSON `{"detail": ...}` shape.
    assert '"detail"' not in body
    # The literal "not found" wording is part of the spec'd 404 page.
    assert "Note not found" in body


def test_get_note_html_escapes_user_input() -> None:
    # XSS boundary: a script tag in the body must be escaped on the way
    # into the HTML page, not rendered as a real <script> element.
    payload = "<script>alert(1)</script>"
    nid = client.post("/notes", json={"body": payload}).json()["id"]
    r = client.get(f"/notes/{nid}/html")
    assert r.status_code == 200, r.text
    body = r.text
    # The raw tag must not appear unescaped.
    assert "<script>alert(1)</script>" not in body
    # The escaped form must appear instead.
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body


def test_get_note_html_does_not_collide_with_import() -> None:
    # Regression guard: GET /notes/import (the literal path-shaping
    # endpoint) must keep working after we added /notes/{note_id}/html.
    # FastAPI's path router must route "import" to the literal route,
    # not the {note_id} parameterised one.
    nid = client.post("/notes", json={"body": "for round trip"}).json()["id"]
    # Export so the import endpoint has something to read.
    client.post("/notes/export", json={"note_id": nid})
    r = client.get("/notes/import", params={"path": f"note_{nid}.txt"})
    assert r.status_code == 200, r.text
    # Import returns the JSON body shape; if the html route had shadowed
    # it, we'd see HTML here instead.
    assert r.headers["content-type"].startswith("application/json"), r.headers
    assert r.json() == {"body": "for round trip"}
