# Project Management MVP Plan

## Goal

Deliver a locally runnable project-management MVP in one Docker container. The application will provide sign-in, one Kanban board per user, editable cards, drag-and-drop ordering, persistent storage, and an AI chat sidebar that can safely update the board.

The existing frontend demo is the starting point. It is a Next.js App Router application with client-owned in-memory state, five columns, drag-and-drop, column renaming, card creation, and card removal. It does not yet provide card editing, authentication, persistence, backend calls, or AI.

## Working Rules

- Complete and verify one phase before starting the next phase.
- Check off each item only after the implementation and its listed tests pass.
- Keep changes small and consistent with the existing frontend patterns.
- Identify the root cause of failures before changing code.
- Do not add features outside the scope below without updating this plan and getting approval.
- Keep secrets in environment variables; never expose the OpenRouter key to the browser or commit it.
- The user must approve this enriched plan before implementation begins.

## Phase 1 Baseline Record

Completed on 2026-09-12 after plan approval:

- `npm run lint`: passed.
- `npm run test:unit`: passed, 6 tests.
- `npm run build`: passed.
- `npm run test:e2e`: initially blocked because the local Playwright Chromium executable was missing; after installing Chromium, passed, 3 tests.
- Plan approval: received from the user on 2026-09-12.

## Decisions Requiring Approval

The original requirements contain a storage ambiguity: they require SQLite, while Part 5 says to save the proposed schema as JSON. The proposed approach is to document the schema in a JSON file and implement the runtime database in normalized SQLite tables. Confirm this before Part 5.

The proposed MVP defaults below are intended to make implementation testable, but remain subject to approval:

- Static serving: build the Next.js frontend as a static export and have FastAPI serve it at `/`.
- Authentication: validate `user` / `password` in FastAPI, issue an HTTP-only session cookie, and clear it on logout.
- Database: SQLite with users, boards, columns, cards, and sessions; create and seed the database on first use.
- Board: one board per user with five fixed columns that users may rename but not add, delete, or reorder.
- Cards: stable ID, title, description, column ID, position, and timestamps.
- API: focused authenticated routes for board reads, column rename, card create/edit/delete, and card move; successful mutations return the updated board.
- Frontend persistence: use server-confirmed mutation responses; show an error and retain the last confirmed state when a save fails.
- AI chat history: keep it in browser session state and send it with each AI request; do not persist chat history in the MVP.
- AI mutations: support the business requirement to create, edit, and move cards; delete operations remain excluded unless separately approved.
- AI safety: validate structured output against the authenticated user and apply a valid set of mutations atomically.

## Phase 1: Planning and Frontend Documentation

### Checklist

- [x] Review the root `AGENTS.md`, this plan, and the current frontend structure.
- [x] Create `frontend/AGENTS.md` describing the App Router structure, board state model, commands, testing locations, and existing conventions.
- [x] Record the approved answers to the Decisions Requiring Approval section in this document.
- [x] Establish baseline results for frontend lint, unit tests, E2E tests, and production build.
- [x] Record baseline failures separately from failures introduced later.
- [x] Get explicit user approval of this plan before beginning Phase 2.

### Tests

- `npm run lint` from `frontend/`.
- `npm run test:unit` from `frontend/`.
- `npm run test:e2e` from `frontend/`.
- `npm run build` from `frontend/`.

### Success Criteria

- `frontend/AGENTS.md` documents the code that actually exists.
- Baseline commands have recorded results.
- The user has approved the enriched plan and resolved the storage and AI scope decisions.

## Phase 2: Docker and FastAPI Scaffolding

Completed on 2026-09-12. Backend tests passed (3 tests), Compose configuration parsed, the Docker image built successfully, and a running container returned the static page plus both API responses. The smoke check needed retries while Uvicorn started; once ready, all requests passed.

### Checklist

- [x] Add a backend `pyproject.toml` managed with `uv`.
- [x] Create a minimal FastAPI application with `/api/health` and an example API route.
- [x] Serve a small static hello-world HTML page at `/`.
- [x] Add a multi-stage Dockerfile that can later build the frontend and run FastAPI.
- [x] Add Docker Compose configuration with port mapping and persistent data volume.
- [x] Add start and stop scripts for macOS/Linux and Windows.
- [x] Keep `.env` out of the image and source control while making runtime variables available to the container.
- [x] Add backend tests for the health route, example API route, and static page.

### Tests

- Backend unit tests with `pytest`.
- `docker compose config`.
- Docker image build.
- Container smoke test verifying `/`, `/api/health`, and the example API route.

### Success Criteria

- A new checkout with the documented prerequisites can start the container using the platform script.
- The static hello page and API route respond on the documented local port.
- The backend test suite passes without requiring an external service.

## Phase 3: Static Frontend Integration

Completed on 2026-09-12. Next static export, FastAPI static mounting, Docker packaging, default development E2E, and production-container E2E all passed. Production E2E uses a health readiness probe before Playwright to avoid a startup race.

### Checklist

- [x] Configure Next.js static export.
- [x] Copy the generated frontend output into the runtime image.
- [x] Have FastAPI serve the generated frontend at `/` and preserve `/api/*` routes.
- [x] Display the existing Kanban demo at the production root URL.
- [x] Keep development and production test commands clearly separated.
- [x] Add or update integration tests for static serving and client hydration.

### Tests

- Frontend unit tests and lint.
- Frontend production build.
- Production-container smoke test for the exported page and API.
- Playwright test against the production serving path.

### Success Criteria

- `/` renders the existing Kanban board from the FastAPI-served static build.
- API routes remain reachable and are not shadowed by frontend routing.
- The production image starts successfully from a clean build.

## Phase 4: Fake User Sign-In

Completed on 2026-09-12. FastAPI now issues an HTTP-only `pm_session` cookie for the hardcoded user, validates the session, supports logout, and protects the session endpoint. The frontend has loading, sign-in, invalid-credential, authenticated, and logout states. Phase 4 sessions are opaque and process-local; Phase 6 will move them into the planned SQLite session table for restart persistence.

### Checklist

- [x] Add the hardcoded `user` / `password` credential check in the backend.
- [x] Add login, logout, and current-session endpoints.
- [x] Choose and document session storage and cookie lifetime.
- [x] Mark board and future AI routes as authentication-required.
- [x] Add frontend login, loading, failure, and logout states.
- [x] Prevent the Kanban from rendering to an unauthenticated user.

### Tests

- Backend tests for valid credentials, invalid credentials, cookie issuance, expired/invalid sessions, logout, and protected routes.
- Frontend component tests for login states.
- Playwright tests for login, refresh while logged in, logout, and rejected unauthenticated access.

### Success Criteria

- Visiting `/` without a valid session shows the sign-in view.
- `user` / `password` allows access to the board.
- Logout invalidates access and returns the user to sign-in.

## Phase 5: Database Model Proposal

Proposal drafted on 2026-09-12 in `docs/database-schema.json` and `docs/DATABASE.md`. JSON validation passed. User approved the schema on 2026-09-13; runtime implementation proceeds in Phase 6.

### Checklist

- [x] Define the schema in a reviewable JSON document under `docs/`.
- [x] Define users, boards, columns, cards, sessions, ownership, ordering, and timestamps.
- [x] Define constraints for one board per user and the five fixed columns.
- [x] Define card title/description validation and ordering semantics.
- [x] Define whether sessions are SQLite-backed or in-memory.
- [x] Document how the JSON proposal maps to runtime SQLite tables.
- [x] Get explicit user sign-off before implementing the schema.

### Tests

- Validate the schema document as JSON.
- Review examples for an empty board, seeded board, card move, and renamed column.
- No runtime database implementation begins until sign-off is recorded.

### Success Criteria

- A reviewer can understand the complete board model without reading application code.
- The JSON proposal and chosen SQLite mapping do not contradict each other.
- User approval is recorded in this plan before Phase 6 starts.

## Phase 6: Persistent Backend Board API

Completed on 2026-09-13. SQLite initialization, idempotent seed data, SQLite-backed sessions, board repository operations, authenticated board routes, and 14 backend tests pass. A production image restart test verified that a created card survives a container restart with the same named volume.

### Checklist

- [x] Initialize SQLite when the database file does not exist.
- [x] Seed the hardcoded user and initial five-column board idempotently.
- [x] Implement repositories/services for board reads and mutations.
- [x] Add authenticated board read route.
- [x] Add column rename route.
- [x] Add card create, edit, delete, and move routes.
- [x] Validate ownership, IDs, required fields, column membership, and ordering.
- [x] Return a consistent board response after every successful mutation.
- [x] Use transactions for mutations that change multiple ordering rows.


### Tests

- Database initialization and idempotent seed tests.
- Route tests for every successful mutation.
- Validation, not-found, unauthorized, and cross-user ownership tests.
- Ordering and transaction rollback tests.
- Restart test proving persisted data survives process/container restart.

### Success Criteria

- A fresh database is created automatically.
- The authenticated user can read and change only their own board.
- Board ordering and edits remain correct after restart.

## Phase 7: Frontend and Backend Persistence

Completed on 2026-09-13. The authenticated frontend now loads the board from the API and uses server-confirmed responses for rename, create, edit, delete, and move operations. It includes recoverable load/save errors and card editing. Frontend unit tests, lint, static build, development E2E, and production-container E2E pass.

### Checklist

- [x] Add a typed frontend API client for authentication and board routes.
- [x] Load the board from the backend after login.
- [x] Replace local-only add, edit, delete, rename, and move operations with API mutations.
- [x] Apply returned server state after successful mutations.
- [x] Handle network and validation failures without losing the last confirmed state.
- [x] Add card editing UI for title and description.
- [x] Preserve accessible keyboard and drag-and-drop behavior.

### Tests

- API client unit tests for success and error responses.
- Component tests for loading, mutation success, and mutation failure.
- Playwright tests for all board actions, refresh persistence, and logout.
- Production-container E2E test using the real SQLite database.

### Success Criteria

- Board changes persist across refresh and container restart.
- Failed saves are visible and do not silently overwrite confirmed data.
- Manual drag-and-drop remains functional.

## Phase 8: OpenRouter Connectivity

Automated Phase 8 implementation completed on 2026-09-13. The backend-only OpenRouter client, configurable free model, protected connectivity route, deterministic failure tests, and `docs/AI.md` are complete. The opt-in live-key check could not be confirmed because the shared terminal stopped returning command output; no live result is being claimed.

Model replaced on 2026-09-14. Root cause of the non-working chat: `nvidia/nemotron-3.5-lightning:free` returned provider 502 errors, leaked reasoning text into answers, and hit the 30-second timeout; it also does not advertise `response_format` support. Free models with structured-output support were benchmarked through the real `/api/ai/*` routes. `nvidia/nemotron-3-super-120b-a12b:free` was the only one that answered `2+2`, a text question, and a create+move request correctly. With reasoning disabled in the request payload, 12 of 12 live calls succeeded: `2+2` in 0.5-3.5s, text answers in 2.5-4s, create+move in 1.7-3.2s.

### Checklist

- [x] Select a currently available free OpenRouter model and record its name and date in the docs.
- [x] Make the model configurable with an environment variable.
- [x] Implement a backend-only OpenRouter client with timeout handling.
- [x] Define behavior for missing key, provider error, rate limit, timeout, and malformed response.
- [x] Add a simple authenticated or development-only `2+2` connectivity check without exposing secrets.
- [x] Use mocked HTTP responses for deterministic automated tests.

### Tests

- Client unit tests for successful response and each defined failure: passed.
- Opt-in live connectivity test using `OPENROUTER_API_KEY`: passed on 2026-09-14 with `nvidia/nemotron-3-super-120b-a12b:free`, locally and in the production container.
- Verify the key is absent from static frontend output and API responses: passed by design; the key is read only by the backend client.

### Success Criteria

- A configured local environment can complete the `2+2` request.
- Automated tests do not require a live API key.
- AI failures produce a useful application error rather than a crash.

## Phase 9: Structured AI Board Operations

Completed on 2026-09-13. The authenticated structured chat route sends board JSON, the question, and bounded history to OpenRouter, validates strict JSON output, supports create/edit/move operations, and applies valid batches atomically. Thirty-two backend tests cover provider, database, authentication, and AI route behavior.

### Checklist

- [x] Define the request containing question, conversation history, and current board JSON.
- [x] Define the structured response containing assistant text and optional operations.
- [x] Define `create_card`, `edit_card`, and `move_card` operation schemas.
- [x] Decide whether operation lookup uses stable IDs, exact names, or both.
- [x] Validate every operation against the authenticated user's board.
- [x] Reject unsupported, malformed, unauthorized, or ambiguous operations.
- [x] Apply a valid operation set atomically and return the updated board.
- [x] Bound conversation history and request size.

### Tests

- Text-only response.
- Create, edit, and move responses.
- Invalid JSON and schema validation.
- Unknown card/column and cross-user ID attempts.
- Multiple-operation atomic success and rollback.
- Provider timeout, rate limit, missing key, and malformed output.

### Success Criteria

- The AI always receives the current authenticated board and user question.
- Only validated operations can change the board.
- Partial AI updates cannot leave the database in an inconsistent state.

## Phase 10: AI Chat Sidebar

Implementation completed on 2026-09-13. The authenticated board now includes a responsive AI sidebar connected to `/api/ai/chat`; conversation history is browser-held, pending/error states are rendered, and the server-returned board replaces local state after AI operations. The static export was switched from Turbopack to webpack because Turbopack emitted relative chunk-loader paths that caused malformed asset requests and left the visible UI unhydrated. Component and deterministic E2E coverage are added.

Verified on 2026-09-14: frontend lint passed, 10 unit/component tests passed, development E2E passed 7 tests, and production-container E2E passed 7 tests on three consecutive runs against a fresh database. Desktop (1440px) and mobile (375px) layouts were checked in a browser. A live AI create+move request against the production container updated the board. Asked to delete cards, the model returned only no-op edits and the board was unchanged. The system prompt now states that deletes are unsupported; that live re-check was blocked by the OpenRouter free-tier daily limit of 50 requests.

One earlier production E2E run failed `moves a card between columns` on a database already modified by manual checks; it did not reproduce on a fresh database or in isolation, so no root cause is claimed.

### Checklist

- [x] Add a responsive sidebar chat widget using the existing visual language.
- [x] Render user and assistant messages with pending and error states.
- [x] Send the question and browser-session conversation history; the backend attaches the authenticated current board.
- [x] Refresh the board from the server when AI operations are applied.
- [x] Keep the chat usable at desktop and mobile widths.
- [x] Add a clear recovery path for failed AI requests.
- [x] Document the AI limitations, including unsupported operations.

### Tests

- Component tests for message rendering and submit states.
- Mocked AI response tests for text-only, create, edit, and move results.
- Playwright tests for chat submission, errors, and automatic board refresh.
- Desktop and mobile layout checks.
- Full production-container E2E workflow.

### Success Criteria

- Users can ask questions without losing board state.
- Valid AI updates appear in the board without a manual page refresh.
- Invalid or failed AI actions are reported without changing the board.

## Final Verification

- [x] Run frontend lint, unit tests, E2E tests, and production build.
- [x] Run backend unit and integration tests (35 passed).
- [x] Build the Docker image from a clean context (`docker compose build --no-cache`).
- [ ] Start and stop it through the platform scripts. macOS shell scripts verified; PowerShell scripts not run.
- [x] Verify first-run database creation and restart persistence.
- [ ] Verify login, logout, board operations, AI chat, and failure paths. All verified except the live delete-refusal re-check, blocked by the free-tier daily limit until 2026-09-15 00:00 UTC.
- [x] Check that secrets are not committed or present in frontend output.
- [x] Update the minimal README and relevant docs with setup and test commands.