from fastapi.testclient import TestClient

from app.database import database
from app import main as main_app
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    database.clear_sessions()
    with database.connect() as connection:
        connection.execute("DELETE FROM cards WHERE id NOT IN ('card-1', 'card-2')")
        connection.execute(
            "UPDATE columns SET title = CASE id "
            "WHEN 'col-backlog' THEN 'Backlog' "
            "WHEN 'col-discovery' THEN 'Discovery' "
            "WHEN 'col-progress' THEN 'In Progress' "
            "WHEN 'col-review' THEN 'Review' "
            "WHEN 'col-done' THEN 'Done' END"
        )
        connection.execute(
            "UPDATE cards SET position = CASE id WHEN 'card-1' THEN -1000000 ELSE -1000001 END "
            "WHERE id IN ('card-1', 'card-2')"
        )
        connection.execute(
            "UPDATE cards SET column_id = 'col-backlog', position = CASE id WHEN 'card-1' THEN 0 ELSE 1 END, "
            "title = CASE id WHEN 'card-1' THEN 'Align roadmap themes' ELSE 'Gather customer signals' END, "
            "description = CASE id WHEN 'card-1' THEN 'Draft quarterly themes with impact statements and metrics.' "
            "ELSE 'Review support tags, sales notes, and churn feedback.' END "
            "WHERE id IN ('card-1', 'card-2')"
        )


def test_health() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_hello() -> None:
    response = client.get("/api/hello")

    assert response.status_code == 200
    assert response.json() == {"message": "Hello from the project management API"}


def test_static_index() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Project Management MVP" in response.text


def test_session_requires_login() -> None:
    response = client.get("/api/auth/session")

    assert response.status_code == 401


def test_login_creates_session_cookie() -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )

    assert response.status_code == 200
    assert response.json() == {"username": "user"}
    assert "pm_session=" in response.headers["set-cookie"]

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json() == {"username": "user"}


def test_invalid_login_is_rejected() -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


def test_logout_invalidates_session() -> None:
    client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )

    logout_response = client.post("/api/auth/logout")

    assert logout_response.status_code == 200
    assert client.get("/api/auth/session").status_code == 401


def test_board_routes_require_authentication() -> None:
    assert client.get("/api/board").status_code == 401


def test_authenticated_board_routes_return_updated_board() -> None:
    client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )

    board_response = client.get("/api/board")
    assert board_response.status_code == 200
    board = board_response.json()
    assert len(board["columns"]) == 5

    rename_response = client.patch(
        "/api/board/columns/col-backlog",
        json={"title": "Ideas"},
    )
    assert rename_response.status_code == 200
    assert rename_response.json()["columns"][0]["title"] == "Ideas"

    create_response = client.post(
        "/api/board/cards",
        json={"column_id": "col-backlog", "title": "API card", "details": "Created by API"},
    )
    assert create_response.status_code == 200
    created_board = create_response.json()
    created_id = next(
        card_id for card_id, card in created_board["cards"].items() if card["title"] == "API card"
    )

    edit_response = client.patch(
        f"/api/board/cards/{created_id}",
        json={"title": "Edited API card", "details": "Updated by API"},
    )
    assert edit_response.status_code == 200
    assert edit_response.json()["cards"][created_id]["title"] == "Edited API card"

    move_response = client.post(
        f"/api/board/cards/{created_id}/move",
        json={"target_column_id": "col-review", "position": 0},
    )
    assert move_response.status_code == 200
    assert created_id in move_response.json()["columns"][3]["cardIds"]

    delete_response = client.delete(f"/api/board/cards/{created_id}")
    assert delete_response.status_code == 200
    assert created_id not in delete_response.json()["cards"]

    client.patch("/api/board/columns/col-backlog", json={"title": "Backlog"})


def test_ai_connectivity_requires_authentication() -> None:
    assert client.post("/api/ai/connectivity").status_code == 401


def test_ai_connectivity_returns_provider_result(monkeypatch) -> None:
    class FakeOpenRouter:
        def connectivity_check(self) -> dict[str, str]:
            return {"model": "test/model:free", "answer": "4"}

    client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    monkeypatch.setattr(main_app, "openrouter", FakeOpenRouter())

    response = client.post("/api/ai/connectivity")

    assert response.status_code == 200
    assert response.json() == {"model": "test/model:free", "answer": "4"}


def test_ai_connectivity_redacts_provider_failure(monkeypatch) -> None:
    class FakeOpenRouter:
        def connectivity_check(self) -> dict[str, str]:
            from app.openrouter import OpenRouterError

            raise OpenRouterError("The AI provider returned an error. Try again shortly.")

    client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    monkeypatch.setattr(main_app, "openrouter", FakeOpenRouter())

    response = client.post("/api/ai/connectivity")

    assert response.status_code == 503
    assert response.json() == {"detail": "The AI provider returned an error. Try again shortly."}


def test_ai_chat_sends_board_and_returns_text_only_response(monkeypatch) -> None:
    class FakeOpenRouter:
        def complete_structured(self, messages, schema):
            prompt = messages[-1]["content"]
            assert "Current board JSON:" in prompt
            assert "What cards are in backlog?" in prompt
            assert schema["required"] == ["message", "operations"]
            return {"message": "There are two cards in backlog.", "operations": []}

    client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    monkeypatch.setattr(main_app, "openrouter", FakeOpenRouter())

    response = client.post(
        "/api/ai/chat",
        json={
            "question": "What cards are in backlog?",
            "history": [{"role": "user", "content": "Hello"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "There are two cards in backlog."
    assert response.json()["operations"] == []
    assert response.json()["board"]["columns"][0]["cardIds"] == ["card-1", "card-2"]


def test_ai_chat_applies_create_edit_and_move(monkeypatch) -> None:
    class FakeOpenRouter:
        def complete_structured(self, messages, schema):
            return {
                "message": "I updated the board.",
                "operations": [
                    {
                        "type": "create_card",
                        "column_id": "col-backlog",
                        "title": "AI task",
                        "details": "Created by AI",
                    },
                    {
                        "type": "edit_card",
                        "card_id": "card-1",
                        "title": "Updated roadmap",
                        "details": None,
                    },
                    {
                        "type": "move_card",
                        "card_id": "card-2",
                        "target_column_id": "col-review",
                        "position": 0,
                    },
                ],
            }

    client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    monkeypatch.setattr(main_app, "openrouter", FakeOpenRouter())

    response = client.post("/api/ai/chat", json={"question": "Update my board."})

    assert response.status_code == 200
    result = response.json()
    assert result["board"]["cards"]["card-1"]["title"] == "Updated roadmap"
    assert result["board"]["cards"]["card-2"]["id"] == "card-2"
    assert result["board"]["columns"][3]["cardIds"] == ["card-2"]
    assert any(card["title"] == "AI task" for card in result["board"]["cards"].values())


def test_ai_chat_rejects_unknown_card_without_partial_update(monkeypatch) -> None:
    class FakeOpenRouter:
        def complete_structured(self, messages, schema):
            return {
                "message": "Attempted update.",
                "operations": [
                    {
                        "type": "create_card",
                        "column_id": "col-backlog",
                        "title": "Should not persist",
                        "details": "",
                    },
                    {
                        "type": "edit_card",
                        "card_id": "missing-card",
                        "title": "Invalid",
                        "details": None,
                    },
                ],
            }

    client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    monkeypatch.setattr(main_app, "openrouter", FakeOpenRouter())

    response = client.post("/api/ai/chat", json={"question": "Make a change."})

    assert response.status_code == 422
    board = client.get("/api/board").json()
    assert all(card["title"] != "Should not persist" for card in board["cards"].values())


def test_ai_chat_rejects_malformed_structured_output(monkeypatch) -> None:
    class FakeOpenRouter:
        def complete_structured(self, messages, schema):
            return {"operations": []}

    client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    monkeypatch.setattr(main_app, "openrouter", FakeOpenRouter())

    response = client.post("/api/ai/chat", json={"question": "Say hello."})

    assert response.status_code == 502
    assert response.json() == {"detail": "The AI returned invalid structured output."}


def test_ai_chat_rejects_unsupported_delete_operation(monkeypatch) -> None:
    class FakeOpenRouter:
        def complete_structured(self, messages, schema):
            return {
                "message": "Delete requested.",
                "operations": [{"type": "delete_card", "card_id": "card-1"}],
            }

    client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    monkeypatch.setattr(main_app, "openrouter", FakeOpenRouter())

    response = client.post("/api/ai/chat", json={"question": "Delete a card."})

    assert response.status_code == 502
    assert response.json() == {"detail": "The AI returned invalid structured output."}


def test_ai_chat_resolves_card_and_column_names(monkeypatch) -> None:
    class FakeOpenRouter:
        def complete_structured(self, messages, schema):
            return {
                "response": "Moved it.",
                "actions": [
                    {
                        "action": "move",
                        "card_title": "Align roadmap themes",
                        "column_name": "In Progress",
                    }
                ],
            }

    client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    monkeypatch.setattr(main_app, "openrouter", FakeOpenRouter())

    response = client.post("/api/ai/chat", json={"question": "Move the roadmap card."})

    assert response.status_code == 200
    assert response.json()["board"]["columns"][2]["cardIds"] == ["card-1"]
