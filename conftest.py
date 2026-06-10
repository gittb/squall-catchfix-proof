"""Test configuration: makes ``app.*`` importable from the repo root and
resets the in-memory notes store around every test so the
export-empty-store test is deterministic regardless of execution order.
"""

from __future__ import annotations

import pytest

from app import main


@pytest.fixture(autouse=True)
def _reset_notes_store() -> None:
    main._NOTES.clear()
    main._NEXT_ID = 1
    yield
    main._NOTES.clear()
    main._NEXT_ID = 1
