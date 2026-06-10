"""Tiny in-memory Notes API — clean baseline for the catch-and-fix proof."""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="notes")

_NOTES: dict[int, str] = {}
_NEXT_ID = 1

# File-I/O surface (catch-and-fix revision):
# All export/import files live under STORAGE_DIR, a per-app sandbox the
# server controls. STORAGE_DIR is resolved to an absolute path under the
# repository working directory and is created on demand. The /notes/import
# endpoint treats its `path` query param as a *basename* only — path
# separators, leading slashes, and ".." segments are rejected — and the
# final file location is recomputed server-side. This prevents callers
# from reading or writing files outside the sandbox (path traversal,
# absolute paths to other roots, symlink escapes).
STORAGE_DIR = os.path.realpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "notes_storage")
)
os.makedirs(STORAGE_DIR, exist_ok=True)


class NoteIn(BaseModel):
    body: str


class ExportIn(BaseModel):
    note_id: int


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/notes")
def create_note(note: NoteIn) -> dict[str, int]:
    global _NEXT_ID
    note_id = _NEXT_ID
    _NOTES[note_id] = note.body
    _NEXT_ID += 1
    return {"id": note_id}


def _safe_join(name: str) -> str:
    """Resolve `name` against STORAGE_DIR and verify the result stays
    inside it. Reject anything that escapes the sandbox.

    Rules (each check raises HTTPException(400) on violation):
    - must be a non-empty string
    - must not contain path separators (``/`` or ``\\``)
    - must not be an absolute path
    - must not be ``.`` or ``..``
    - the resolved absolute path must still be inside STORAGE_DIR
      (defence in depth against symlink escapes)

    Returns the absolute path on success.
    """
    if not isinstance(name, str) or name == "":
        raise HTTPException(status_code=400, detail="path is required")
    if "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="path must not contain separators")
    if os.path.isabs(name):
        raise HTTPException(status_code=400, detail="path must be relative")
    if name in (".", ".."):
        raise HTTPException(status_code=400, detail="path must not be . or ..")
    full = os.path.realpath(os.path.join(STORAGE_DIR, name))
    if not (full == STORAGE_DIR or full.startswith(STORAGE_DIR + os.sep)):
        raise HTTPException(status_code=400, detail="path resolves outside the sandbox")
    return full


def _read_file(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write_file(path: str, body: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)


@app.post("/notes/export")
def export_note(payload: ExportIn) -> dict[str, str]:
    # Empty-store behaviour is defined explicitly: an empty store is a
    # 404, not a KeyError/500. An unknown note_id is also a 404.
    if not _NOTES:
        raise HTTPException(status_code=404, detail="no notes to export")
    if payload.note_id not in _NOTES:
        raise HTTPException(status_code=404, detail="note not found")
    body = _NOTES[payload.note_id]
    full = _safe_join(f"note_{payload.note_id}.txt")
    try:
        _write_file(full, body)
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="export failed: file not found")
    except (PermissionError, OSError):
        raise HTTPException(status_code=400, detail="export failed: file system error")
    return {"written": os.path.relpath(full, STORAGE_DIR)}


@app.get("/notes/import")
def import_note(path: str) -> dict[str, str]:
    full = _safe_join(path)  # raises 400 on validation failure
    try:
        body = _read_file(full)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="file not found")
    except (PermissionError, OSError):
        raise HTTPException(status_code=400, detail="import failed: file system error")
    return {"body": body}


@app.get("/notes/{note_id}")
def get_note(note_id: int) -> dict[str, str]:
    if note_id not in _NOTES:
        raise HTTPException(status_code=404, detail="not found")
    return {"body": _NOTES[note_id]}
