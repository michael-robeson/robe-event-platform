from __future__ import annotations

import base64
import binascii
import json
import logging
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from robe_event_platform.database import DatabaseSettings

logger = logging.getLogger(__name__)
Consumer = Literal["item", "audit"]
CONSUMERS: tuple[Consumer, ...] = ("item", "audit")


def connect(settings: DatabaseSettings) -> psycopg.Connection[Any]:
    return psycopg.connect(
        host=settings.host, port=settings.port, dbname=settings.dbname,
        user=settings.user, password=settings.password, connect_timeout=3,
        row_factory=dict_row, options="-c statement_timeout=3000 -c default_transaction_read_only=on",
    )


def item_list(connection: psycopg.Connection[Any], cursor: tuple[datetime, UUID, str] | None, limit: int) -> list[dict[str, Any]]:
    return list(connection.execute(
        """
        SELECT event_id, event_type, contract_version, source, occurred_at,
               processed_at AS recorded_at, 'item' AS consumer
        FROM item_projection.processed_event
        WHERE (%s::timestamptz IS NULL OR (processed_at, event_id) < (%s, %s)
               OR (processed_at, event_id) = (%s, %s) AND 'item' < %s)
        ORDER BY processed_at DESC, event_id DESC LIMIT %s
        """,
        (cursor[0] if cursor else None, cursor[0] if cursor else None,
         cursor[1] if cursor else None, cursor[0] if cursor else None,
         cursor[1] if cursor else None, cursor[2] if cursor else None, limit),
    ).fetchall())


def audit_list(connection: psycopg.Connection[Any], cursor: tuple[datetime, UUID, str] | None, limit: int) -> list[dict[str, Any]]:
    return list(connection.execute(
        """
        SELECT event_id, event_type, contract_version, source, occurred_at,
               recorded_at, 'audit' AS consumer
        FROM audit_projection.audit_event
        WHERE (%s::timestamptz IS NULL OR (recorded_at, event_id) < (%s, %s)
               OR (recorded_at, event_id) = (%s, %s) AND 'audit' < %s)
        ORDER BY recorded_at DESC, event_id DESC LIMIT %s
        """,
        (cursor[0] if cursor else None, cursor[0] if cursor else None,
         cursor[1] if cursor else None, cursor[0] if cursor else None,
         cursor[1] if cursor else None, cursor[2] if cursor else None, limit),
    ).fetchall())


def item_detail(connection: psycopg.Connection[Any], event_id: UUID) -> dict[str, Any] | None:
    connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
    row = connection.execute(
        """
        SELECT event_id, event_type, contract_version, occurred_at, source,
               correlation_id, causation_id, processed_at, encode(canonical_content_hash, 'hex') AS content_hash
        FROM item_projection.processed_event WHERE event_id = %s
        """, (event_id,),
    ).fetchone()
    projection = connection.execute(
        """
        SELECT source, item_id, label, registered_event_id
        FROM item_projection.item_projection WHERE registered_event_id = %s
        """, (event_id,),
    ).fetchone()
    if row is None and projection is None:
        return None
    return {"ledger": row, "projection": projection}


def audit_detail(connection: psycopg.Connection[Any], event_id: UUID) -> dict[str, Any] | None:
    return connection.execute(
        """
        SELECT event_id, event_type, contract_version, occurred_at, source,
               correlation_id, causation_id, item_id, label, recorded_at,
               encode(canonical_content_hash, 'hex') AS content_hash
        FROM audit_projection.audit_event WHERE event_id = %s
        """, (event_id,),
    ).fetchone()


LIST_READERS = {"item": item_list, "audit": audit_list}
DETAIL_READERS = {"item": item_detail, "audit": audit_detail}


def encode_cursor(row: dict[str, Any], consumers: list[str]) -> str:
    value = [row["recorded_at"].isoformat(), str(row["event_id"]), row["consumer"], consumers]
    return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode()


def decode_cursor(value: str, consumers: list[str]) -> tuple[datetime, UUID, str]:
    try:
        decoded = json.loads(base64.b64decode(value.encode("ascii"), altchars=b"-_", validate=True))
        if (
            not isinstance(decoded, list) or len(decoded) != 4
            or not all(isinstance(part, str) for part in decoded[:3])
            or decoded[2] not in consumers or decoded[3] != consumers
        ):
            raise ValueError("Invalid cursor")
        timestamp = datetime.fromisoformat(decoded[0])
        if timestamp.utcoffset() is None:
            raise ValueError("Invalid cursor timestamp")
        return timestamp, UUID(decoded[1]), decoded[2]
    except (ValueError, TypeError, UnicodeError, binascii.Error, json.JSONDecodeError) as error:
        raise ValueError("Invalid cursor") from error


def observations(settings: DatabaseSettings, consumers: list[str], limit: int, cursor: tuple[datetime, UUID, str] | None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    sources: dict[str, str] = {}
    for consumer in consumers:
        try:
            with connect(settings) as connection:
                source_rows = LIST_READERS[consumer](connection, cursor, limit + 1)
            rows.extend(source_rows)
            sources[consumer] = "available"
        except psycopg.Error:
            logger.exception("Could not read %s observations", consumer)
            sources[consumer] = "unknown"
    rows.sort(key=lambda row: (row["recorded_at"], row["event_id"], row["consumer"]), reverse=True)
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit and all(status == "available" for status in sources.values()):
        next_cursor = encode_cursor(page[-1], consumers)
    return {"observations": page, "sources": sources, "next_cursor": next_cursor}


def event_detail(settings: DatabaseSettings, event_id: UUID) -> dict[str, Any]:
    sources: dict[str, dict[str, Any]] = {}
    for consumer in CONSUMERS:
        try:
            with connect(settings) as connection:
                record = DETAIL_READERS[consumer](connection, event_id)
            sources[consumer] = {
                "status": "record_observed" if record else "not_observed",
                "record": record,
            }
        except psycopg.Error:
            logger.exception("Could not read %s event record", consumer)
            sources[consumer] = {"status": "unknown", "record": None}
    return {"event_id": event_id, "sources": sources}
