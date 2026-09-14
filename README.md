# Project Management MVP

Kanban board with sign-in and an AI chat sidebar. FastAPI serves the static Next.js build; data is stored in SQLite.

## Setup

Create `.env` in the project root:

```
OPENROUTER_API_KEY=your-key
```

Optional: `OPENROUTER_MODEL` overrides the default free model.

## Run

```bash
./scripts/start.sh
```

Open http://localhost:8000 and sign in with `user` / `password`. Stop with `./scripts/stop.sh`. On Windows use `scripts/start.ps1` and `scripts/stop.ps1`.

## Tests

```bash
cd backend && uv run pytest
cd frontend && npm run lint && npm run test:unit && npm run build && npm run test:e2e
```

Production E2E against a running container: `PLAYWRIGHT_BASE_URL=http://127.0.0.1:8000 npm run test:e2e`.
