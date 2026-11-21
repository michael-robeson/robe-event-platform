from __future__ import annotations

import os
from dataclasses import dataclass

import psycopg
from psycopg.errors import UniqueViolation

from robe_event_platform.events import ItemRegisteredEvent, canonical_event_hash


class EventIdentityConflict(Exception):
    """An event ID was reused for different semantic content."""


class BusinessKeyConflict(Exception):
    """A different event conflicts with an existing source-scoped item."""


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    dbname: str
    user: str
    password: str

    @classmethod
    def from_environment(cls) -> DatabaseSettings:
        required = (
            "DATABASE_HOST",
            "DATABASE_NAME",
            "DATABASE_USER",
            "DATABASE_PASSWORD",
        )
        missing = [key for key in required if not os.environ.get(key)]
        if missing:
            raise RuntimeError(f"Missing database settings: {', '.join(missing)}")
        if os.environ["DATABASE_HOST"] != "postgres":
            raise RuntimeError(
                "DATABASE_HOST must be the local Compose service 'postgres'"
            )
        return cls(
            host="postgres",
            port=int(os.environ.get("DATABASE_PORT", "5432")),
            dbname=os.environ["DATABASE_NAME"],
            user=os.environ["DATABASE_USER"],
            password=os.environ["DATABASE_PASSWORD"],
        )

    def connect(self) -> psycopg.Connection[tuple]:
        return psycopg.connect(
            host=self.host,
            port=self.port,
            dbname=self.dbname,
            user=self.user,
            password=self.password,
            autocommit=False,
        )


def apply_event(
    settings: DatabaseSettings, event: ItemRegisteredEvent
) -> bool:
    """Persist an event atomically; return False when it was an exact duplicate."""
    digest = canonical_event_hash(event)
    with settings.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO item_projection.processed_event (
                    event_id,
                    event_type,
                    contract_version,
                    occurred_at,
                    source,
                    correlation_id,
                    causation_id,
                    canonical_content_hash
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO NOTHING
                RETURNING event_id
                """,
                (
                    event.event_id,
                    event.event_type,
                    event.contract_version,
                    event.occurred_at,
                    event.source,
                    event.correlation_id,
                    event.causation_id,
                    digest,
                ),
            )
            inserted = cursor.fetchone()
            if inserted is None:
                cursor.execute(
                    """
                    SELECT canonical_content_hash
                    FROM item_projection.processed_event
                    WHERE event_id = %s
                    """,
                    (event.event_id,),
                )
                existing = cursor.fetchone()
                if existing is None:
                    raise psycopg.errors.SerializationFailure(
                        "Conflicting event disappeared during deduplication"
                    )
                if bytes(existing[0]) != digest:
                    raise EventIdentityConflict(str(event.event_id))
                return False

            try:
                cursor.execute(
                    """
                    INSERT INTO item_projection.item_projection (
                        source,
                        item_id,
                        label,
                        registered_event_id
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        event.source,
                        event.payload.item_id,
                        event.payload.label,
                        event.event_id,
                    ),
                )
            except UniqueViolation as error:
                raise BusinessKeyConflict(
                    f"Item key already exists for source {event.source!r}"
                ) from error
    return True
