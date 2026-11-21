from __future__ import annotations

import psycopg

from robe_event_platform.database import DatabaseSettings, EventIdentityConflict
from robe_event_platform.events import ItemRegisteredEvent, canonical_event_hash


def apply_audit_event(settings: DatabaseSettings, event: ItemRegisteredEvent) -> bool:
    digest = canonical_event_hash(event)
    with settings.connect() as connection:
        inserted = connection.execute(
            """
            INSERT INTO audit_projection.audit_event (
                event_id, event_type, contract_version, occurred_at, source,
                item_id, label, correlation_id, causation_id, canonical_content_hash
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO NOTHING
            RETURNING event_id
            """,
            (
                event.event_id,
                event.event_type,
                event.contract_version,
                event.occurred_at,
                event.source,
                event.payload.item_id,
                event.payload.label,
                event.correlation_id,
                event.causation_id,
                digest,
            ),
        ).fetchone()
        if inserted is None:
            existing = connection.execute(
                """
                SELECT canonical_content_hash FROM audit_projection.audit_event
                WHERE event_id = %s
                """,
                (event.event_id,),
            ).fetchone()
            if existing is None:
                raise psycopg.errors.SerializationFailure(
                    "Conflicting audit event disappeared during deduplication"
                )
            if bytes(existing[0]) != digest:
                raise EventIdentityConflict(str(event.event_id))
            return False
    return True
