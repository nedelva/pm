from datetime import datetime, timedelta, timezone
import sqlite3

from app.database import Database, timestamp


def test_initialize_is_idempotent_and_seeds_board(tmp_path) -> None:
    database = Database(tmp_path / "project.sqlite3")

    database.initialize()
    database.initialize()

    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM boards").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM columns").fetchone()[0] == 5
        assert connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 2

    board = database.get_board("user")
    assert [column["title"] for column in board["columns"]] == [
        "Backlog",
        "Discovery",
        "In Progress",
        "Review",
        "Done",
    ]
    assert board["columns"][0]["cardIds"] == ["card-1", "card-2"]


def test_session_survives_new_database_instance(tmp_path) -> None:
    database = Database(tmp_path / "project.sqlite3")
    database.initialize()

    user_id = database.authenticate("user", "password")
    assert user_id is not None
    session_id = database.create_session(user_id)

    reopened = Database(database.path)
    assert reopened.get_session_user(session_id) == "user"

    reopened.delete_session(session_id)
    assert database.get_session_user(session_id) is None


def test_expired_sessions_are_rejected_and_cleaned(tmp_path) -> None:
    database = Database(tmp_path / "project.sqlite3")
    database.initialize()
    user_id = database.authenticate("user", "password")
    assert user_id is not None

    with database.connect() as connection:
        connection.execute(
            "INSERT INTO sessions (id, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (
                "expired-session",
                user_id,
                timestamp(datetime.now(timezone.utc) - timedelta(seconds=1)),
                timestamp(datetime.now(timezone.utc)),
            ),
        )

    assert database.get_session_user("expired-session") is None
    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM sessions WHERE id = ?", ("expired-session",)
        ).fetchone()[0] == 0


def test_foreign_keys_are_enabled(tmp_path) -> None:
    database = Database(tmp_path / "project.sqlite3")
    database.initialize()

    with database.connect() as connection:
        try:
            connection.execute(
                "INSERT INTO cards (id, board_id, column_id, title, description, position, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("orphan", "missing-board", "missing-column", "Orphan", "", 0, "now", "now"),
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("Foreign-key constraints are disabled")


def test_board_mutations_preserve_order_and_ownership(tmp_path) -> None:
    database = Database(tmp_path / "project.sqlite3")
    database.initialize()

    renamed = database.rename_column("user", "col-backlog", "Ideas")
    assert renamed["columns"][0]["title"] == "Ideas"

    created = database.create_card("user", "col-backlog", "New task", "Details")
    created_id = next(
        card_id for card_id, card in created["cards"].items() if card["title"] == "New task"
    )
    assert created["columns"][0]["cardIds"] == ["card-1", "card-2", created_id]

    edited = database.edit_card("user", created_id, "Edited task", "Updated")
    assert edited["cards"][created_id] == {
        "id": created_id,
        "title": "Edited task",
        "details": "Updated",
    }

    moved = database.move_card("user", created_id, "col-review", 0)
    assert moved["columns"][0]["cardIds"] == ["card-1", "card-2"]
    assert moved["columns"][3]["cardIds"] == [created_id]

    deleted = database.delete_card("user", created_id)
    assert created_id not in deleted["cards"]
    assert deleted["columns"][3]["cardIds"] == []

    for operation in (
        lambda: database.rename_column("missing", "col-backlog", "Nope"),
        lambda: database.create_card("missing", "col-backlog", "Nope", ""),
        lambda: database.edit_card("missing", "card-1", "Nope", ""),
        lambda: database.delete_card("missing", "card-1"),
        lambda: database.move_card("missing", "card-1", "col-review", 0),
    ):
        try:
            operation()
        except ValueError:
            pass
        else:
            raise AssertionError("Cross-user board operation was accepted")


def test_ai_operations_are_atomic(tmp_path) -> None:
    database = Database(tmp_path / "project.sqlite3")
    database.initialize()

    try:
        database.apply_ai_operations(
            "user",
            [
                {
                    "type": "create_card",
                    "column_id": "col-backlog",
                    "title": "Should roll back",
                    "details": "",
                },
                {
                    "type": "move_card",
                    "card_id": "missing-card",
                    "target_column_id": "col-review",
                    "position": 0,
                },
            ],
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid AI operation batch was accepted")

    board = database.get_board("user")
    assert all(card["title"] != "Should roll back" for card in board["cards"].values())
