# Frontend Guide

The frontend is a Next.js App Router application using TypeScript and React. The current demo renders the Kanban board from `src/app/page.tsx`; board behavior and state helpers live in `src/components/` and `src/lib/kanban.ts`.

## Commands

Run these from `frontend/`:

- `npm run dev` starts the Next.js development server.
- `npm run build` creates the production build.
- `npm run lint` runs ESLint.
- `npm run test:unit` runs Vitest unit and component tests.
- `npm run test:e2e` runs Playwright browser tests.
- `npm run test:all` runs unit tests followed by E2E tests.

## Testing

Unit and component tests belong beside the implementation under `src/` and use the jsdom setup in `src/test/setup.ts`. Browser tests belong in `tests/`. Keep board transformations covered at the library level and user workflows covered with Testing Library or Playwright.

## Conventions

Preserve the normalized board shape: columns own ordered `cardIds`, while cards are stored by ID. Keep drag-and-drop behavior in the existing `@dnd-kit` implementation. Prefer focused changes that preserve the current component structure and visual language.
