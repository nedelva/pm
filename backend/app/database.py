from __future__ import annotations

import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = BASE_DIR / "data"
SESSION_MAX_AGE = 60 * 60 * 8

SEED_COLUMNS = (
    ("col-backlog", "Backlog", 0),
    ("col-discovery", "Discovery", 1),
    ("col-progress", "In Progress", 2),
    ("col-review", "Review", 3),
    ("col-done", "Done", 4),
)
SEED_CARDS = (
    (
        "card-1",
        "col-backlog",
        "Align roadmap themes",
        "Draft quarterly themes with impact statements and metrics.",
        0,
    ),
    (
        "card-2",
        "col-backlog",
        "Gather customer signals",
        "Review support tags, sales notes, and churn feedback.",
        1,
    ),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS boards (
    id TEXT PRIMARY KEY,
    user_id TEXT UNIQUE NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS columns (
    id TEXT PRIMARY KEY,
    board_id TEXT NOT NULL REFERENCES boards(id),
    title TEXT NOT NULL,
    position INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(board_id, position)
);
CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    board_id TEXT NOT NULL REFERENCES boards(id),
    column_id TEXT NOT NULL REFERENCES columns(id),
    title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 200),
    description TEXT NOT NULL DEFAULT '' CHECK(length(description) <= 2000),
    position INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(column_id, position),
    FOREIGN KEY(column_id) REFERENCES columns(id)
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cards_board ON cards(board_id);
CREATE INDEX IF NOT EXISTS idx_cards_column ON cards(column_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
"""


def now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(value: datetime) -> str:
    return value.isoformat()


class Database:
    def __init__(self, path: str | Path | None = None) -> None:
        configured_dir = Path(os.getenv("DATA_DIR", DEFAULT_DATA_DIR))
        self.path = Path(path) if path is not None else configured_dir / "project-management.sqlite3"

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            self._seed(connection)

    def _seed(self, connection: sqlite3.Connection) -> None:
        current_time = timestamp(now())
        connection.execute(
            "INSERT OR IGNORE INTO users (id, username, password, created_at) VALUES (?, ?, ?, ?)",
            ("user-1", "user", "password", current_time),
        )
        user = connection.execute(
            "SELECT id FROM users WHERE username = ?", ("user",)
        ).fetchone()
        if user is None:
            raise RuntimeError("Seed user was not created")

        connection.execute(
            "INSERT OR IGNORE INTO boards (id, user_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("board-1", user["id"], current_time, current_time),
        )
        board = connection.execute(
            "SELECT id FROM boards WHERE user_id = ?", (user["id"],)
        ).fetchone()
        if board is None:
            raise RuntimeError("Seed board was not created")

        for column_id, title, position in SEED_COLUMNS:
            connection.execute(
                """
                INSERT OR IGNORE INTO columns
                    (id, board_id, title, position, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (column_id, board["id"], title, position, current_time, current_time),
            )
        for card_id, column_id, title, description, position in SEED_CARDS:
            connection.execute(
                """
                INSERT OR IGNORE INTO cards
                    (id, board_id, column_id, title, description, position, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    card_id,
                    board["id"],
                    column_id,
                    title,
                    description,
                    position,
                    current_time,
                    current_time,
                ),
            )

    def authenticate(self, username: str, password: str) -> str | None:
        with self.connect() as connection:
            user = connection.execute(
                "SELECT id FROM users WHERE username = ? AND password = ?",
                (username, password),
            ).fetchone()
        return user["id"] if user else None

    def create_session(self, user_id: str) -> str:
        session_id = secrets.token_urlsafe(32)
        current_time = now()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO sessions (id, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (
                    session_id,
                    user_id,
                    timestamp(current_time + timedelta(seconds=SESSION_MAX_AGE)),
                    timestamp(current_time),
                ),
            )
        return session_id

    def get_session_user(self, session_id: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT users.username
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.id = ? AND sessions.expires_at > ?
                """,
                (session_id, timestamp(now())),
            ).fetchone()
            connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (timestamp(now()),))
        return row["username"] if row else None

    def delete_session(self, session_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def clear_sessions(self) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM sessions")

    def get_board(self, username: str) -> dict[str, Any]:
        with self.connect() as connection:
            board = self._get_board_row(connection, username)
            if board is None:
                raise ValueError("Board not found")

            columns = connection.execute(
                "SELECT id, title FROM columns WHERE board_id = ? ORDER BY position",
                (board["id"],),
            ).fetchall()
            cards = connection.execute(
                """
                SELECT id, column_id, title, description, position
                FROM cards
                WHERE board_id = ?
                ORDER BY column_id, position
                """,
                (board["id"],),
            ).fetchall()

        cards_by_id = {
            card["id"]: {
                "id": card["id"],
                "title": card["title"],
                "details": card["description"],
            }
            for card in cards
        }
        cards_by_column: dict[str, list[str]] = {column["id"]: [] for column in columns}
        for card in cards:
            cards_by_column[card["column_id"]].append(card["id"])

        return {
            "id": board["id"],
            "columns": [
                {
                    "id": column["id"],
                    "title": column["title"],
                    "cardIds": cards_by_column[column["id"]],
                }
                for column in columns
            ],
            "cards": cards_by_id,
        }

    def _get_board_row(
        self, connection: sqlite3.Connection, username: str
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT boards.id
            FROM boards
            JOIN users ON users.id = boards.user_id
            WHERE users.username = ?
            """,
            (username,),
        ).fetchone()

    def rename_column(self, username: str, column_id: str, title: str) -> dict[str, Any]:
        normalized_title = title.strip()
        if not normalized_title or len(normalized_title) > 100:
            raise ValueError("Column title must be between 1 and 100 characters")
        with self.connect() as connection:
            board = self._get_board_row(connection, username)
            updated = connection.execute(
                "UPDATE columns SET title = ?, updated_at = ? WHERE id = ? AND board_id = ?",
                (normalized_title, timestamp(now()), column_id, board["id"] if board else ""),
            ).rowcount
            if board is None or updated == 0:
                raise ValueError("Column not found")
            connection.execute(
                "UPDATE boards SET updated_at = ? WHERE id = ?",
                (timestamp(now()), board["id"]),
            )
        return self.get_board(username)

    def create_card(
        self, username: str, column_id: str, title: str, description: str
    ) -> dict[str, Any]:
        normalized_title = title.strip()
        normalized_description = description.strip()
        self._validate_card_fields(normalized_title, normalized_description)
        card_id = f"card-{secrets.token_urlsafe(12)}"
        current_time = timestamp(now())
        with self.connect() as connection:
            board = self._get_board_row(connection, username)
            if board is None:
                raise ValueError("Board not found")
            column = connection.execute(
                "SELECT id FROM columns WHERE id = ? AND board_id = ?",
                (column_id, board["id"]),
            ).fetchone()
            if column is None:
                raise ValueError("Column not found")
            position = connection.execute(
                "SELECT COALESCE(MAX(position) + 1, 0) FROM cards WHERE column_id = ?",
                (column_id,),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO cards
                    (id, board_id, column_id, title, description, position, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (card_id, board["id"], column_id, normalized_title, normalized_description, position, current_time, current_time),
            )
            connection.execute(
                "UPDATE boards SET updated_at = ? WHERE id = ?",
                (current_time, board["id"]),
            )
        return self.get_board(username)

    def edit_card(
        self,
        username: str,
        card_id: str,
        title: str | None,
        description: str | None,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            board = self._get_board_row(connection, username)
            if board is None:
                raise ValueError("Board not found")
            card = connection.execute(
                "SELECT title, description FROM cards WHERE id = ? AND board_id = ?",
                (card_id, board["id"]),
            ).fetchone()
            if card is None:
                raise ValueError("Card not found")
            next_title = card["title"] if title is None else title.strip()
            next_description = card["description"] if description is None else description.strip()
            self._validate_card_fields(next_title, next_description)
            current_time = timestamp(now())
            connection.execute(
                "UPDATE cards SET title = ?, description = ?, updated_at = ? WHERE id = ? AND board_id = ?",
                (next_title, next_description, current_time, card_id, board["id"]),
            )
            connection.execute(
                "UPDATE boards SET updated_at = ? WHERE id = ?",
                (current_time, board["id"]),
            )
        return self.get_board(username)

    def delete_card(self, username: str, card_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            board = self._get_board_row(connection, username)
            if board is None:
                raise ValueError("Board not found")
            card = connection.execute(
                "SELECT column_id FROM cards WHERE id = ? AND board_id = ?",
                (card_id, board["id"]),
            ).fetchone()
            if card is None:
                raise ValueError("Card not found")
            connection.execute("DELETE FROM cards WHERE id = ?", (card_id,))
            self._compact_column(connection, card["column_id"])
            connection.execute(
                "UPDATE boards SET updated_at = ? WHERE id = ?",
                (timestamp(now()), board["id"]),
            )
        return self.get_board(username)

    def move_card(
        self, username: str, card_id: str, target_column_id: str, position: int
    ) -> dict[str, Any]:
        if position < 0:
            raise ValueError("Position must not be negative")
        with self.connect() as connection:
            board = self._get_board_row(connection, username)
            if board is None:
                raise ValueError("Board not found")
            card = connection.execute(
                "SELECT column_id FROM cards WHERE id = ? AND board_id = ?",
                (card_id, board["id"]),
            ).fetchone()
            target = connection.execute(
                "SELECT id FROM columns WHERE id = ? AND board_id = ?",
                (target_column_id, board["id"]),
            ).fetchone()
            if card is None:
                raise ValueError("Card not found")
            if target is None:
                raise ValueError("Column not found")

            source_column_id = card["column_id"]
            source_cards = self._card_ids(connection, source_column_id, card_id)
            if source_column_id == target_column_id:
                source_cards.insert(min(position, len(source_cards)), card_id)
                self._clear_positions(connection, source_column_id)
                self._write_positions(connection, source_column_id, source_cards)
            else:
                target_cards = self._card_ids(connection, target_column_id)
                target_cards.insert(min(position, len(target_cards)), card_id)
                self._clear_positions(connection, source_column_id)
                self._clear_positions(connection, target_column_id)
                connection.execute(
                    "UPDATE cards SET column_id = ?, position = -1000000 WHERE id = ?",
                    (target_column_id, card_id),
                )
                self._write_positions(connection, source_column_id, source_cards)
                self._write_positions(connection, target_column_id, target_cards)
            connection.execute(
                "UPDATE boards SET updated_at = ? WHERE id = ?",
                (timestamp(now()), board["id"]),
            )
        return self.get_board(username)

    def apply_ai_operations(
        self, username: str, operations: list[dict[str, Any]]
    ) -> dict[str, Any]:
        current_time = timestamp(now())
        with self.connect() as connection:
            board = self._get_board_row(connection, username)
            if board is None:
                raise ValueError("Board not found")

            for operation in operations:
                operation_type = operation.get("type")
                if operation_type == "create_card":
                    self._apply_create_operation(connection, board["id"], operation, current_time)
                elif operation_type == "edit_card":
                    self._apply_edit_operation(connection, board["id"], operation, current_time)
                elif operation_type == "move_card":
                    self._apply_move_operation(connection, board["id"], operation, current_time)
                else:
                    raise ValueError("Unsupported AI operation")

            connection.execute(
                "UPDATE boards SET updated_at = ? WHERE id = ?",
                (current_time, board["id"]),
            )
        return self.get_board(username)

    @staticmethod
    def _apply_create_operation(
        connection: sqlite3.Connection,
        board_id: str,
        operation: dict[str, Any],
        current_time: str,
    ) -> None:
        title = str(operation["title"]).strip()
        description = str(operation.get("details", "")).strip()
        Database._validate_card_fields(title, description)
        column_id = operation["column_id"]
        if connection.execute(
            "SELECT 1 FROM columns WHERE id = ? AND board_id = ?", (column_id, board_id)
        ).fetchone() is None:
            raise ValueError("Column not found")
        position = connection.execute(
            "SELECT COALESCE(MAX(position) + 1, 0) FROM cards WHERE column_id = ?",
            (column_id,),
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO cards
                (id, board_id, column_id, title, description, position, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"card-{secrets.token_urlsafe(12)}",
                board_id,
                column_id,
                title,
                description,
                position,
                current_time,
                current_time,
            ),
        )

    @staticmethod
    def _apply_edit_operation(
        connection: sqlite3.Connection,
        board_id: str,
        operation: dict[str, Any],
        current_time: str,
    ) -> None:
        card = connection.execute(
            "SELECT title, description FROM cards WHERE id = ? AND board_id = ?",
            (operation["card_id"], board_id),
        ).fetchone()
        if card is None:
            raise ValueError("Card not found")
        if operation.get("title") is None and operation.get("details") is None:
            raise ValueError("Edit operation must change title or details")
        title = card["title"] if operation.get("title") is None else str(operation["title"]).strip()
        description = (
            card["description"]
            if operation.get("details") is None
            else str(operation["details"]).strip()
        )
        Database._validate_card_fields(title, description)
        connection.execute(
            "UPDATE cards SET title = ?, description = ?, updated_at = ? WHERE id = ? AND board_id = ?",
            (title, description, current_time, operation["card_id"], board_id),
        )

    @staticmethod
    def _apply_move_operation(
        connection: sqlite3.Connection,
        board_id: str,
        operation: dict[str, Any],
        current_time: str,
    ) -> None:
        position = int(operation["position"])
        if position < 0:
            raise ValueError("Position must not be negative")
        card = connection.execute(
            "SELECT column_id FROM cards WHERE id = ? AND board_id = ?",
            (operation["card_id"], board_id),
        ).fetchone()
        target = connection.execute(
            "SELECT id FROM columns WHERE id = ? AND board_id = ?",
            (operation["target_column_id"], board_id),
        ).fetchone()
        if card is None:
            raise ValueError("Card not found")
        if target is None:
            raise ValueError("Column not found")

        source_column_id = card["column_id"]
        target_column_id = operation["target_column_id"]
        source_cards = Database._card_ids(connection, source_column_id, operation["card_id"])
        if source_column_id == target_column_id:
            source_cards.insert(min(position, len(source_cards)), operation["card_id"])
            Database._clear_positions(connection, source_column_id)
            Database._write_positions(connection, source_column_id, source_cards)
        else:
            target_cards = Database._card_ids(connection, target_column_id)
            target_cards.insert(min(position, len(target_cards)), operation["card_id"])
            Database._clear_positions(connection, source_column_id)
            Database._clear_positions(connection, target_column_id)
            connection.execute(
                "UPDATE cards SET column_id = ?, position = -1000000, updated_at = ? WHERE id = ?",
                (target_column_id, current_time, operation["card_id"]),
            )
            Database._write_positions(connection, source_column_id, source_cards)
            Database._write_positions(connection, target_column_id, target_cards)

    @staticmethod
    def _validate_card_fields(title: str, description: str) -> None:
        if not 1 <= len(title) <= 200:
            raise ValueError("Card title must be between 1 and 200 characters")
        if len(description) > 2000:
            raise ValueError("Card description must be at most 2000 characters")

    @staticmethod
    def _card_ids(
        connection: sqlite3.Connection, column_id: str, excluded_id: str | None = None
    ) -> list[str]:
        query = "SELECT id FROM cards WHERE column_id = ?"
        parameters: tuple[str, ...] = (column_id,)
        if excluded_id is not None:
            query += " AND id != ?"
            parameters += (excluded_id,)
        rows = connection.execute(query + " ORDER BY position", parameters).fetchall()
        return [row["id"] for row in rows]

    @staticmethod
    def _write_positions(
        connection: sqlite3.Connection, column_id: str, card_ids: list[str]
    ) -> None:
        for position, card_id in enumerate(card_ids):
            connection.execute(
                "UPDATE cards SET position = ?, column_id = ? WHERE id = ?",
                (position, column_id, card_id),
            )

    @staticmethod
    def _clear_positions(connection: sqlite3.Connection, column_id: str) -> None:
        rows = connection.execute(
            "SELECT id FROM cards WHERE column_id = ? ORDER BY position", (column_id,)
        ).fetchall()
        for position, row in enumerate(rows):
            connection.execute(
                "UPDATE cards SET position = ? WHERE id = ?",
                (-(position + 1), row["id"]),
            )

    @staticmethod
    def _compact_column(connection: sqlite3.Connection, column_id: str) -> None:
        Database._clear_positions(connection, column_id)
        Database._write_positions(connection, column_id, Database._card_ids(connection, column_id))


database = Database()
database.initialize()
