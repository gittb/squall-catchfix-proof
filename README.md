# seeded-bad-pr fixture — a deliberately-vulnerable Notes API

The M5.5 Slice 2 seeded-bad-PR battery class force-pushes this tree as a branch
and opens a PR against it, so a `code_reviewer` + `security_reviewer` (pod-with-
checkout, §7 #64) must CATCH the seeded flaws and route the PR to a fix-worker
(the §7 #83 catch-and-fix loop). It freezes the exact pair from the 2026-06-10
proof so the catch is reproducible verbatim — no worker-writes variance.

## Seeded flaws (the reviewer must flag both as BLOCKING)

| Flaw | Class | Where | Reproduce |
|---|---|---|---|
| Path traversal | security `critical` / OWASP `path_traversal` | `app/main.py` `/notes/export`, `/notes/import` (raw `?path=` file read) | `GET /notes/export?path=/etc/hostname` returns the host file |
| KeyError crash | code `blocker` | `app/main.py` `/notes/latest` (`_NOTES[_NEXT_ID - 1]` off-by-one) | `GET /notes/latest` on an empty store → 500 |

## Run it (what the reviewer does)

This tree has no `pyproject.toml` (it's a fixture, not a uv project), so use a venv:

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8080
curl 'http://localhost:8080/notes/export?path=/etc/hostname'   # leaks the host
curl 'http://localhost:8080/notes/latest'                      # 500 KeyError
```

## The expected fix (what the fix-worker pushes)

Sandbox the path under a notes directory (reject `..` / absolute paths) and guard
the empty-store case in `/notes/latest`. The battery asserts the reviewer's
catch-time verdict was `request_changes` with the path-traversal rated `critical`
and the crash rated `blocker` — the Axis-1 calibration (a reproduced exploit must
BLOCK, not pass non-blocking; the voting-demo#5 failure mode the §7 #83 cure fixed).

This is NOT production code; it is a maintained eval fixture.
