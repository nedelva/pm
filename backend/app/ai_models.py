from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class CreateCardOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["create_card"]
    column_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    details: str = Field(default="", max_length=2000)


class EditCardOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["edit_card"]
    card_id: str = Field(min_length=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    details: str | None = Field(default=None, max_length=2000)


class MoveCardOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["move_card"]
    card_id: str = Field(min_length=1)
    target_column_id: str = Field(min_length=1)
    position: int = Field(ge=0)


BoardOperation = Annotated[
    CreateCardOperation | EditCardOperation | MoveCardOperation,
    Field(discriminator="type"),
]


class AIChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class AIChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=8000)
    operations: list[BoardOperation] = Field(default_factory=list, max_length=20)


AI_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "message": {"type": "string", "minLength": 1, "maxLength": 8000},
        "operations": {
            "type": "array",
            "maxItems": 20,
            "items": {
                "anyOf": [
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "type": {"const": "create_card"},
                            "column_id": {"type": "string", "minLength": 1},
                            "title": {"type": "string", "minLength": 1, "maxLength": 200},
                            "details": {"type": "string", "maxLength": 2000},
                        },
                        "required": ["type", "column_id", "title", "details"],
                    },
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "type": {"const": "edit_card"},
                            "card_id": {"type": "string", "minLength": 1},
                            "title": {"type": ["string", "null"], "maxLength": 200},
                            "details": {"type": ["string", "null"], "maxLength": 2000},
                        },
                        "required": ["type", "card_id", "title", "details"],
                    },
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "type": {"const": "move_card"},
                            "card_id": {"type": "string", "minLength": 1},
                            "target_column_id": {"type": "string", "minLength": 1},
                            "position": {"type": "integer", "minimum": 0},
                        },
                        "required": ["type", "card_id", "target_column_id", "position"],
                    },
                ]
            },
        },
    },
    "required": ["message", "operations"],
}
