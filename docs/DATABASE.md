# Database Approach

The runtime database will be SQLite. The schema proposal is recorded in [database-schema.json](database-schema.json) so it can be reviewed independently of the Python implementation.

## Runtime Model

The database uses normalized `users`, `boards`, `columns`, `cards`, and `sessions` tables. Each user has one board. Each board is seeded with five stable columns. Cards reference both their board and column and use integer positions that are unique within their column.

The API will return the frontend's normalized board shape: columns contain ordered `card_ids`, while cards are keyed by ID. Repository code will translate between that response shape and the normalized tables.

## Initialization

The backend will create the SQLite file and tables if they do not exist, then seed the hardcoded MVP user, one board, five columns, and example cards idempotently. Existing user changes must never be overwritten during startup.

## Sessions

Sessions are stored in SQLite with an expiry timestamp. Session IDs remain opaque and are sent only in an HTTP-only cookie. The database is initialized and seeded automatically when the backend starts.

## Approval Gate

Runtime schema implementation must wait for user sign-off on [database-schema.json](database-schema.json), especially:

- the normalized table boundaries and one-board-per-user constraint;
- title and description length limits;
- fixed five-column behavior;
- integer position ordering;
- SQLite-backed sessions in Phase 6.
