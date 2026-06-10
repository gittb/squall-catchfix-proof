"""Tiny in-memory Notes API — clean baseline for the catch-and-fix proof."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="notes")

_NOTES: dict[int, str] = {}
_NEXT_ID = 1


class NoteIn(BaseModel):
    body: str


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


@app.get("/notes/{note_id}")
def get_note(note_id: int) -> dict[str, str]:
    if note_id not in _NOTES:
        raise HTTPException(status_code=404, detail="not found")
    return {"body": _NOTES[note_id]}
