from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path

import psycopg
from psycopg import sql

from robe_event_platform.database import DatabaseSettings

MIGRATION_FILE = Path("/app/services/audit_consumer/db/001_initial.sql")
MIGRATION_VERSION = 1


def migrate() -> None:
    settings = DatabaseSettings.from_environment()
    app_password = os.environ.get("AUDIT_PROJECTION_DB_PASSWORD")
    if not app_password:
        raise RuntimeError("AUDIT_PROJECTION_DB_PASSWORD is required")
    migration = MIGRATION_FILE.read_bytes()
    checksum = sha256(migration).hexdigest()

    with settings.connect() as connection:
        connection.execute("SELECT pg_advisory_xact_lock(722619401)")
        schema = connection.execute(
            "SELECT to_regnamespace('audit_projection')"
        ).fetchone()
        if schema is None:
            raise RuntimeError("Could not check audit schema")

        if schema[0] is None:
            existing_roles = connection.execute(
                """
                SELECT rolname FROM pg_roles
                WHERE rolname IN ('audit_projection_owner', 'audit_projection_app')
                """
            ).fetchall()
            if existing_roles:
                raise RuntimeError("Audit roles already exist without their schema")
            connection.execute("CREATE ROLE audit_projection_owner NOLOGIN")
            connection.execute(
                sql.SQL("CREATE ROLE audit_projection_app LOGIN PASSWORD {}").format(
                    sql.Literal(app_password)
                )
            )
            connection.execute(
                "CREATE SCHEMA audit_projection AUTHORIZATION audit_projection_owner"
            )
            connection.execute("SET LOCAL ROLE audit_projection_owner")
            connection.execute(
                """
                CREATE TABLE audit_projection.schema_migrations (
                    version INTEGER PRIMARY KEY,
                    checksum TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(migration.decode("utf-8"))
            connection.execute(
                """
                INSERT INTO audit_projection.schema_migrations (version, checksum)
                VALUES (%s, %s)
                """,
                (MIGRATION_VERSION, checksum),
            )
        else:
            metadata = connection.execute(
                """
                SELECT pg_get_userbyid(nspowner),
                       to_regclass('audit_projection.schema_migrations')
                FROM pg_namespace WHERE nspname = 'audit_projection'
                """
            ).fetchone()
            if metadata is None or metadata[0] != "audit_projection_owner" or metadata[1] is None:
                raise RuntimeError("Existing audit schema is not managed by this migration")
            versions = connection.execute(
                "SELECT version, checksum FROM audit_projection.schema_migrations"
            ).fetchall()
            if versions != [(MIGRATION_VERSION, checksum)]:
                raise RuntimeError("Audit migration version or checksum does not match")

    with psycopg.connect(
        host=settings.host,
        port=settings.port,
        dbname=settings.dbname,
        user="audit_projection_app",
        password=app_password,
    ) as connection:
        connection.execute("SELECT event_id FROM audit_projection.audit_event LIMIT 0")


if __name__ == "__main__":
    migrate()
