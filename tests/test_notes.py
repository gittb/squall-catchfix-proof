from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_create_and_get_note() -> None:
    nid = client.post("/notes", json={"body": "hello"}).json()["id"]
    assert client.get(f"/notes/{nid}").json() == {"body": "hello"}
