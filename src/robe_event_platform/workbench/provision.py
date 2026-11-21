from __future__ import annotations

import os

import psycopg
from psycopg import sql

from robe_event_platform.database import DatabaseSettings

ROLE = "workbench_reader"
MARKER = "robe-event-platform local workbench reader"


def provision() -> None:
    settings = DatabaseSettings.from_environment()
    password = os.environ.get("WORKBENCH_DB_PASSWORD")
    if not password:
        raise RuntimeError("WORKBENCH_DB_PASSWORD is required")
    with settings.connect() as connection:
        connection.execute("SELECT pg_advisory_xact_lock(722619402)")
        role = connection.execute(
            """
            SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
                   rolreplication, rolbypassrls, shobj_description(oid, 'pg_authid')
            FROM pg_roles WHERE rolname = %s
            """,
            (ROLE,),
        ).fetchone()
        if role is None:
            connection.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(ROLE), sql.Literal(password)
                )
            )
            connection.execute(
                sql.SQL("COMMENT ON ROLE {} IS {}").format(
                    sql.Identifier(ROLE), sql.Literal(MARKER)
                )
            )
        elif role != (True, False, False, False, False, False, MARKER):
            raise RuntimeError("Existing workbench role is not the expected local reader")
        memberships = connection.execute(
            """
            SELECT 1 FROM pg_auth_members m
            JOIN pg_roles r ON r.oid = m.member WHERE r.rolname = %s
            """,
            (ROLE,),
        ).fetchone()
        if memberships:
            raise RuntimeError("Workbench reader must not inherit other roles")
        connection.execute("GRANT USAGE ON SCHEMA item_projection, audit_projection TO workbench_reader")
        connection.execute(
            """
            GRANT SELECT ON item_projection.processed_event,
                item_projection.item_projection, audit_projection.audit_event
            TO workbench_reader
            """
        )
        connection.execute(
            "ALTER ROLE workbench_reader SET default_transaction_read_only = on"
        )
        for table in (
            "item_projection.processed_event",
            "item_projection.item_projection",
            "audit_projection.audit_event",
        ):
            unsafe = connection.execute(
                """
                SELECT has_table_privilege(%s, %s, 'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                """,
                (ROLE, table),
            ).fetchone()
            if unsafe is None or unsafe[0]:
                raise RuntimeError(f"Workbench reader has unsafe privileges on {table}")
        for schema in ("item_projection", "audit_projection"):
            unsafe = connection.execute(
                "SELECT has_schema_privilege(%s, %s, 'CREATE')", (ROLE, schema)
            ).fetchone()
            if unsafe is None or unsafe[0]:
                raise RuntimeError(f"Workbench reader can create objects in {schema}")

    with psycopg.connect(
        host=settings.host, port=settings.port, dbname=settings.dbname,
        user=ROLE, password=password, connect_timeout=3,
    ) as connection:
        for table in (
            "item_projection.processed_event",
            "item_projection.item_projection",
            "audit_projection.audit_event",
        ):
            connection.execute(sql.SQL("SELECT 1 FROM {} LIMIT 0").format(
                sql.Identifier(*table.split("."))
            ))


if __name__ == "__main__":
    provision()
