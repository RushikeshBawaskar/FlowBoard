from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

MAX_BOARD_NAME_LENGTH = 255
MAX_CARD_TITLE_LENGTH = 255
MAX_CARD_DESCRIPTION_LENGTH = 2000


class CardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    list_id: uuid.UUID
    title: str
    description: str | None
    position_rank: Decimal

    @field_serializer("position_rank")
    def serialize_rank(self, value: Decimal, _info: Any) -> str:
        return str(value)


class ListRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    board_id: uuid.UUID
    name: str
    position_rank: Decimal
    cards: list[CardRead]

    @field_serializer("position_rank")
    def serialize_rank(self, value: Decimal, _info: Any) -> str:
        return str(value)


class BoardSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class BoardDetailRead(BoardSummaryRead):
    lists: list[ListRead]


class BoardCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_BOARD_NAME_LENGTH)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if normalized == "":
            raise ValueError("Board name is required.")
        return normalized


class BoardUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_BOARD_NAME_LENGTH)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if normalized == "":
            raise ValueError("Board name is required.")
        return normalized


class CardCreateRequest(BaseModel):
    list_id: uuid.UUID
    title: str = Field(min_length=1, max_length=MAX_CARD_TITLE_LENGTH)
    description: str | None = Field(default=None, max_length=MAX_CARD_DESCRIPTION_LENGTH)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        normalized = value.strip()
        if normalized == "":
            raise ValueError("Card title is required.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized if normalized != "" else None


class CardUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=MAX_CARD_TITLE_LENGTH)
    description: str | None = Field(default=None, max_length=MAX_CARD_DESCRIPTION_LENGTH)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if normalized == "":
            raise ValueError("Card title cannot be empty.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized if normalized != "" else None


class CardMoveRequest(BaseModel):
    target_list_id: uuid.UUID
    prev_card_id: uuid.UUID | None = None
    next_card_id: uuid.UUID | None = None


class CardMoveRead(BaseModel):
    card_id: uuid.UUID
    board_id: uuid.UUID
    list_id: uuid.UUID
