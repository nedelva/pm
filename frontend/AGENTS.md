# Frontend Guide

The frontend is a Next.js App Router application using TypeScript and React, built as a static export (`output: "export"`) that FastAPI serves at `/`. All data comes from the backend API; there is no Next.js server code.

## Structure

- `src/app/page.tsx` renders `AuthenticatedApp`.
- `src/components/AuthenticatedApp.tsx` checks `/api/auth/session`, shows the loading and sign-in views, and renders the board once signed in.
- `src/components/KanbanBoard.tsx` loads the board, handles column rename, card create/edit/delete, and `@dnd-kit` drag-and-drop, and hosts the AI sidebar.
- `src/components/KanbanColumn.tsx`, `KanbanCard.tsx`, `KanbanCardPreview.tsx`, `NewCardForm.tsx` are the board building blocks.
- `src/components/AIChatSidebar.tsx` holds the chat history in component state, sends the question plus the last 20 messages to `/api/ai/chat`, and passes the returned board to `onBoardUpdate`.
- `src/lib/api.ts` is the typed API client. Requests include cookies and use `NEXT_PUBLIC_API_BASE_URL` as a prefix (empty in production, `http://127.0.0.1:8000` in development).
- `src/lib/kanban.ts` defines the board types, seed data, and the local `moveCard` transformation.

## State Model

The board shape is normalized: columns own ordered `cardIds`, while cards are stored by ID. The server is the source of truth: every mutation calls the API and replaces local state with the returned board. On failure, show the error and keep the last confirmed board.

## Commands

Run these from `frontend/`:

- `npm run dev` starts the Next.js development server.
- `npm run build` creates the static export in `out/` (uses webpack; Turbopack produced broken chunk paths in the export).
- `npm run lint` runs ESLint.
- `npm run test:unit` runs Vitest unit and component tests.
- `npm run test:e2e` runs Playwright browser tests.
- `npm run test:all` runs unit tests followed by E2E tests.

## Testing

Unit and component tests belong beside the implementation under `src/` and use the jsdom setup in `src/test/setup.ts`; mock `fetch` for API calls. Browser tests belong in `tests/`.

By default Playwright starts the backend on port 8000 and the dev server on port 3000, reusing any server already listening. Make sure no Docker container is holding port 8000, or tests will run against it. To test a production container, set `PLAYWRIGHT_BASE_URL` (for example `http://127.0.0.1:8000`) and no servers are started. The chat E2E test mocks `/api/ai/chat`, so it needs no API key.

## Conventions

Keep drag-and-drop in the existing `@dnd-kit` implementation. Use the color scheme from the root `AGENTS.md`. Prefer focused changes that preserve the current component structure and visual language.
