# Backend Guide

The backend is a Python FastAPI application managed with `uv`. It serves the JSON API under `/api/*`, the static Next.js export at `/`, and stores data in SQLite.

## Structure

- `app/main.py` defines the FastAPI app, request models, the `current_user` session dependency, all routes, and the AI chat flow. It mounts `static/next` (the frontend export copied in by the Dockerfile) at `/`, or falls back to `static/index.html` when the export is absent.
- `app/database.py` holds the `Database` class and the module-level `database` instance. On import it creates the schema and seeds the `user` / `password` account, `board-1`, five fixed columns, and two cards. Seeding is idempotent.
- `app/openrouter.py` is the backend-only OpenRouter client with safe, user-facing `OpenRouterError` messages.
- `app/ai_models.py` holds the Pydantic models for chat requests, responses, and card operations, plus the JSON Schema sent to the provider.

## Data

SQLite tables: users, boards, columns, cards, sessions (see `docs/DATABASE.md` and `docs/database-schema.json`). The database file is `project-management.sqlite3` in `DATA_DIR` (default `backend/data/`, `/app/data` in Docker). Sessions are stored in SQLite, use an HTTP-only `pm_session` cookie, and expire after 8 hours. Card and column order is kept in integer `position` columns; multi-row changes run in one transaction.

## API

- `GET /api/health`, `GET /api/hello`: unauthenticated.
- `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/session`.
- `GET /api/board`, `PATCH /api/board/columns/{id}`, `POST /api/board/cards`, `PATCH /api/board/cards/{id}`, `DELETE /api/board/cards/{id}`, `POST /api/board/cards/{id}/move`. Every mutation returns the full updated board.
- `POST /api/ai/connectivity`: authenticated `2+2` check against the configured model.
- `POST /api/ai/chat`: sends the system prompt, up to 20 history messages, the current board JSON, and the question to OpenRouter. The reply is normalized, card titles and column names are resolved to IDs, validated, and `create_card` / `edit_card` / `move_card` operations are applied atomically. Deletes are not supported.

## AI Configuration

`OPENROUTER_API_KEY` is required for live AI calls; `OPENROUTER_MODEL` overrides the default `nvidia/nemotron-3-super-120b-a12b:free`. Requests use temperature 0 and disable reasoning for fast answers. If the provider rejects the JSON Schema `response_format`, the client retries once with a JSON-only instruction. See `docs/AI.md`.

## Commands

Run from `backend/`:

- `uv sync` installs dependencies.
- `uv run uvicorn app.main:app --app-dir . --host 127.0.0.1 --port 8000` runs the API locally.
- `uv run pytest` runs the tests.

## Testing

Tests live in `tests/`: `test_database.py` (schema, seed, ordering, rollback), `test_main.py` (auth, board routes, AI chat route), and `test_openrouter.py` (client success and failure paths). OpenRouter calls are mocked with `httpx.MockTransport`, so tests never need a live key. Use `Database(tmp_path / "project.sqlite3")` when a test needs a fresh database.
