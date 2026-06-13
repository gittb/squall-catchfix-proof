"""A deliberately-vulnerable Notes API — the M5.5 Slice 2 seeded-bad-PR fixture.

This is NOT production code. It is a maintained proof-of-state artifact: the
exact pair of flaws the 2026-06-10 catch-and-fix proof seeded, frozen here so the
seeded-bad-PR battery class reproduces them verbatim every run (no worker-writes
variance). A code_reviewer + security_reviewer cloning this branch must CATCH both:

  1. SECURITY (path traversal, OWASP path_traversal): `/notes/export` and
     `/notes/import` read/write a raw user-controlled `?path=` off disk with no
     sandboxing. Reproduce: `GET /notes/export?path=/etc/hostname` returns the host.
  2. CODE BLOCKER (crash): `/notes/latest` does `_NOTES[_NEXT_ID - 1]`, which
     KeyErrors (500) on an empty store — the off-by-one the reviewer must flag.

The fix (what the fix-worker should push) sandboxes the path under a notes dir and
guards the empty-store case. The battery asserts the reviewer rated these BLOCKING
(blocker / critical) under request_changes — the Axis-1 calibration (§7 #83).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Notes API (seeded-bad-pr fixture)")

_NOTES: dict[int, str] = {}
_NEXT_ID = 1


class NoteIn(BaseModel):
    body: str


@app.post("/notes")
def create_note(note: NoteIn) -> dict[str, int | str]:
    global _NEXT_ID
    note_id = _NEXT_ID
    _NOTES[note_id] = note.body
    _NEXT_ID += 1
    return {"id": note_id, "body": note.body}


@app.get("/notes/{note_id}")
def get_note(note_id: int) -> dict[str, int | str]:
    return {"id": note_id, "body": _NOTES.get(note_id, "")}


@app.get("/notes/latest")
def latest_note() -> dict[str, int | str]:
    # CODE BLOCKER: KeyErrors (500) on an empty store — `_NEXT_ID - 1` is 0 before
    # any note exists, and 0 is never a key. Off-by-one with no empty-store guard.
    last_id = _NEXT_ID - 1
    return {"id": last_id, "body": _NOTES[last_id]}


@app.get("/notes/export")
def export_notes(path: str) -> dict[str, str]:
    # SECURITY (path traversal): raw user path read off disk, no sandboxing.
    # `GET /notes/export?path=/etc/hostname` leaks arbitrary files.
    return {"path": path, "contents": Path(path).read_text()}


@app.post("/notes/import")
def import_notes(path: str) -> dict[str, str]:
    # SECURITY (path traversal): raw user path written/read, no sandboxing.
    contents = Path(path).read_text()
    return {"path": path, "imported_bytes": str(len(contents))}
