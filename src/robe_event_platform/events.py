from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Literal
from uuid import UUID

import rfc8785
from pydantic import BaseModel, ConfigDict, field_serializer, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ItemRegisteredPayload(StrictModel):
    item_id: str
    label: str

    @field_validator("item_id", "label")
    @classmethod
    def require_nonempty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be a nonempty string")
        return value


class ItemRegisteredEvent(StrictModel):
    event_id: UUID
    event_type: Literal["demo.item.registered"]
    contract_version: Literal["1"]
    occurred_at: datetime
    source: str
    payload: ItemRegisteredPayload
    correlation_id: str | None = None
    causation_id: str | None = None

    @field_validator("source", "correlation_id", "causation_id")
    @classmethod
    def require_nonempty_optional_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("must be a nonempty string when provided")
        return value

    @field_validator("occurred_at")
    @classmethod
    def require_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("occurred_at must include a UTC offset")
        return value.astimezone(timezone.utc)

    @field_serializer("occurred_at")
    def serialize_occurred_at(self, value: datetime) -> str:
        return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def canonical_event_bytes(event: ItemRegisteredEvent) -> bytes:
    event_content = event.model_dump(mode="json", exclude_none=True)
    return rfc8785.dumps(event_content)


def canonical_event_hash(event: ItemRegisteredEvent) -> bytes:
    return sha256(canonical_event_bytes(event)).digest()
