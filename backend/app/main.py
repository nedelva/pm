from pathlib import Path
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from app.database import database
from app.ai_models import AIChatRequest, AIChatResponse, AI_RESPONSE_SCHEMA
from app.openrouter import OpenRouterClient, OpenRouterError
import json

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
FRONTEND_DIR = STATIC_DIR / "next"
SESSION_COOKIE = "pm_session"
SESSION_MAX_AGE = 60 * 60 * 8
openrouter = OpenRouterClient()

app = FastAPI(title="Project Management API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def prevent_stale_app_shell(request, call_next):
    response = await call_next(request)
    if request.url.path == "/":
        response.headers["Cache-Control"] = "no-store"
    return response


class LoginRequest(BaseModel):
    username: str
    password: str


class RenameColumnRequest(BaseModel):
    title: str


class CreateCardRequest(BaseModel):
    column_id: str
    title: str
    details: str = ""


class EditCardRequest(BaseModel):
    title: str | None = None
    details: str | None = None


class MoveCardRequest(BaseModel):
    target_column_id: str
    position: int


def current_user(
    session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> str:
    if session_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    username = database.get_session_user(session_id)
    if username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return username


def normalize_ai_response(raw_response: dict) -> dict:
    response = dict(raw_response)
    if "message" not in response and isinstance(response.get("response"), str):
        response["message"] = response.pop("response")
    raw_operations = response.get("operations", response.get("actions", []))
    normalized_operations = []
    for raw_operation in raw_operations:
        operation = dict(raw_operation)
        operation_type = operation.get("type", operation.get("action"))
        operation["type"] = {
            "create": "create_card",
            "edit": "edit_card",
            "move": "move_card",
        }.get(operation_type, operation_type)
        operation.pop("action", None)
        if operation["type"] in ("edit_card", "move_card") and "card_id" not in operation:
            operation["card_id"] = operation.pop("card", operation.pop("card_title", None))
        if operation["type"] == "create_card" and "column_id" not in operation:
            operation["column_id"] = operation.pop("column", operation.pop("column_name", None))
        if operation["type"] == "move_card":
            if "target_column_id" not in operation:
                operation["target_column_id"] = operation.pop(
                    "target_column", operation.pop("column", operation.pop("column_name", None))
                )
            operation.setdefault("position", 0)
        if "details" not in operation and "description" in operation:
            operation["details"] = operation.pop("description")
        normalized_operations.append(operation)
    return {"message": response.get("message"), "operations": normalized_operations}


def resolve_ai_ids(response: AIChatResponse, board_data: dict) -> AIChatResponse:
    columns = {
        value.lower(): column_id
        for column in board_data["columns"]
        for value, column_id in ((column["id"], column["id"]), (column["title"], column["id"]))
    }
    cards = {
        value.lower(): card_id
        for card_id, card in board_data["cards"].items()
        for value in (card_id, card["title"])
    }
    resolved = []
    for operation in response.operations:
        values = operation.model_dump()
        if "card_id" in values and values["card_id"]:
            values["card_id"] = cards.get(values["card_id"].lower(), values["card_id"])
        for field in ("column_id", "target_column_id"):
            if field in values and values[field]:
                values[field] = columns.get(values[field].lower(), values[field])
        resolved.append(values)
    return AIChatResponse.model_validate({"message": response.message, "operations": resolved})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": "Hello from the project management API"}


@app.post("/api/auth/login")
def login(payload: LoginRequest, response: Response) -> dict[str, str]:
    user_id = database.authenticate(payload.username, payload.password)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    session_id = database.create_session(user_id)
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return {"username": payload.username}


@app.get("/api/auth/session")
def session(username: Annotated[str, Depends(current_user)]) -> dict[str, str]:
    return {"username": username}


@app.post("/api/auth/logout")
def logout(
    response: Response,
    session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, str]:
    if session_id is not None:
        database.delete_session(session_id)
    response.delete_cookie(SESSION_COOKIE)
    return {"status": "ok"}


@app.get("/api/board")
def board(username: Annotated[str, Depends(current_user)]) -> dict:
    return database.get_board(username)


@app.patch("/api/board/columns/{column_id}")
def rename_column(
    column_id: str,
    payload: RenameColumnRequest,
    username: Annotated[str, Depends(current_user)],
) -> dict:
    try:
        return database.rename_column(username, column_id, payload.title)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@app.post("/api/board/cards")
def create_card(
    payload: CreateCardRequest,
    username: Annotated[str, Depends(current_user)],
) -> dict:
    try:
        return database.create_card(username, payload.column_id, payload.title, payload.details)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


@app.patch("/api/board/cards/{card_id}")
def edit_card(
    card_id: str,
    payload: EditCardRequest,
    username: Annotated[str, Depends(current_user)],
) -> dict:
    try:
        return database.edit_card(username, card_id, payload.title, payload.details)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@app.delete("/api/board/cards/{card_id}")
def delete_card(
    card_id: str,
    username: Annotated[str, Depends(current_user)],
) -> dict:
    try:
        return database.delete_card(username, card_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@app.post("/api/board/cards/{card_id}/move")
def move_card(
    card_id: str,
    payload: MoveCardRequest,
    username: Annotated[str, Depends(current_user)],
) -> dict:
    try:
        return database.move_card(username, card_id, payload.target_column_id, payload.position)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


@app.post("/api/ai/connectivity")
def ai_connectivity(username: Annotated[str, Depends(current_user)]) -> dict:
    del username
    try:
        return openrouter.connectivity_check()
    except OpenRouterError as error:
        detail = str(error)
        if error.provider_status == 401:
            detail = "The AI provider rejected the backend API key. Check OPENROUTER_API_KEY."
        elif error.provider_status == 404:
            detail = "The configured AI model is unavailable. Check OPENROUTER_MODEL."
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail) from error


@app.post("/api/ai/chat")
def ai_chat(
    payload: AIChatRequest,
    username: Annotated[str, Depends(current_user)],
) -> dict:
    board_data = database.get_board(username)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a project management assistant. Answer the user's question and, "
                "when requested, propose only create_card, edit_card, or move_card operations. "
                "Match natural-language card titles and column names to the exact stable IDs "
                "in the board JSON. Never invent IDs. If a move has no requested position, use 0. "
                "Return JSON matching the provided schema."
            ),
        },
        *[message.model_dump() for message in payload.history],
        {
            "role": "user",
            "content": (
                f"Current board JSON:\n{json.dumps(board_data, separators=(',', ':'))}\n\n"
                f"User question:\n{payload.question}"
            ),
        },
    ]
    try:
        raw_response = openrouter.complete_structured(messages, AI_RESPONSE_SCHEMA)
        ai_response = resolve_ai_ids(
            AIChatResponse.model_validate(normalize_ai_response(raw_response)),
            board_data,
        )
        updated_board = database.apply_ai_operations(
            username,
            [operation.model_dump() for operation in ai_response.operations],
        )
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="The AI returned invalid structured output.") from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except OpenRouterError as error:
        detail = str(error)
        if error.provider_status == 401:
            detail = "The AI provider rejected the backend API key. Check OPENROUTER_API_KEY."
        elif error.provider_status == 404:
            detail = "The configured AI model is unavailable. Check OPENROUTER_MODEL."
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail) from error

    return {
        "message": ai_response.message,
        "operations": [operation.model_dump() for operation in ai_response.operations],
        "board": updated_board,
    }


if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")
