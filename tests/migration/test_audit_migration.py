from __future__ import annotations

import subprocess
from uuid import uuid4

from tests.e2e.test_audit_consumer import admin_connection
from tests.e2e.test_vertical_slice import ROOT, database_connection


def test_audit_migration_preserves_existing_item_data_and_is_repeatable() -> None:
    event_id = uuid4()
    item_id = f"migration-{uuid4()}"
    with database_connection() as connection:
        connection.execute(
            """
            INSERT INTO item_projection.processed_event
                (event_id, event_type, contract_version, occurred_at, source,
                 canonical_content_hash)
            VALUES (%s, 'demo.item.registered', '1', '2026-11-20T12:00:00Z',
                    'migration-test', %s)
            """,
            (event_id, bytes(32)),
        )
        connection.execute(
            """
            INSERT INTO item_projection.item_projection
                (source, item_id, label, registered_event_id)
            VALUES ('migration-test', %s, 'preserved', %s)
            """,
            (item_id, event_id),
        )

    for _ in range(2):
        subprocess.run(
            [
                "docker",
                "compose",
                "--profile",
                "demo",
                "-f",
                "compose.yaml",
                "-f",
                "compose.demo.yaml",
                "run",
                "--rm",
                "--no-deps",
                "audit-migrate",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        with database_connection() as connection:
            assert connection.execute(
                """
                SELECT label, registered_event_id
                FROM item_projection.item_projection
                WHERE source = 'migration-test' AND item_id = %s
                """,
                (item_id,),
            ).fetchone() == ("preserved", event_id)
            assert connection.execute(
                "SELECT event_id FROM item_projection.processed_event WHERE event_id = %s",
                (event_id,),
            ).fetchone() == (event_id,)
        with admin_connection() as connection:
            assert connection.execute(
                "SELECT version FROM audit_projection.schema_migrations"
            ).fetchall() == [(1,)]
