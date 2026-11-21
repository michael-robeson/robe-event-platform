from __future__ import annotations

import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest

from tests.e2e.test_vertical_slice import (
    SOURCE,
    database_connection,
    make_event,
    publish,
    push_wrapper,
    read_projection,
    wait_for_projection,
    wait_until,
)

AUDIT_URL = "http://127.0.0.1:8082"
ITEM_PROXY = "http://127.0.0.1:9001"
AUDIT_PROXY = "http://127.0.0.1:9002"


def admin_connection() -> psycopg.Connection[tuple]:
    password = os.environ.get("POSTGRES_ADMIN_PASSWORD")
    if not password:
        raise RuntimeError("POSTGRES_ADMIN_PASSWORD is required for audit tests")
    return psycopg.connect(
        host="127.0.0.1",
        port=55432,
        dbname="robe_events",
        user="robe_admin",
        password=password,
    )


def audit_connection() -> psycopg.Connection[tuple]:
    password = os.environ.get("AUDIT_PROJECTION_DB_PASSWORD")
    if not password:
        raise RuntimeError("AUDIT_PROJECTION_DB_PASSWORD is required for audit tests")
    return psycopg.connect(
        host="127.0.0.1",
        port=55432,
        dbname="robe_events",
        user="audit_projection_app",
        password=password,
    )


def read_audit(event_id: str) -> list[tuple[Any, ...]]:
    with admin_connection() as connection:
        return connection.execute(
            """
            SELECT event_id, source, item_id, label, canonical_content_hash
            FROM audit_projection.audit_event WHERE event_id = %s
            """,
            (UUID(event_id),),
        ).fetchall()


def wait_for_audit(event_id: str) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []

    def exists() -> bool:
        nonlocal rows
        rows = read_audit(event_id)
        return bool(rows)

    wait_until(exists)
    return rows


def proxy_command(proxy: str, command: str) -> None:
    response = httpx.post(f"{proxy}/__test/{command}", timeout=5)
    response.raise_for_status()


def proxy_status(proxy: str, event_id: str) -> dict[str, int]:
    response = httpx.get(f"{proxy}/__test/status/{event_id}", timeout=5)
    response.raise_for_status()
    return response.json()


def test_fanout_persists_independent_projections() -> None:
    event = make_event()
    publish(event)

    item = wait_for_projection(event)
    audit = wait_for_audit(event["event_id"])
    assert item[0][2:] == (event["payload"]["label"], UUID(event["event_id"]))
    assert audit[0][:4] == (
        UUID(event["event_id"]),
        event["source"],
        event["payload"]["item_id"],
        event["payload"]["label"],
    )
    assert len(audit[0][4]) == 32


@pytest.mark.parametrize("blocked", ["item", "audit"])
def test_one_consumer_recovers_after_the_other_progresses(blocked: str) -> None:
    event = make_event()
    event_id = event["event_id"]
    proxy = ITEM_PROXY if blocked == "item" else AUDIT_PROXY
    proxy_command(proxy, "hold")
    try:
        publish(event)
        wait_until(lambda: proxy_status(proxy, event_id)["deliveries"] >= 1)
        if blocked == "item":
            wait_for_audit(event_id)
            assert read_projection(SOURCE, event["payload"]["item_id"]) == []
        else:
            wait_for_projection(event)
            assert read_audit(event_id) == []
    finally:
        proxy_command(proxy, "release")

    assert len(wait_for_projection(event)) == 1
    assert len(wait_for_audit(event_id)) == 1


def test_duplicate_publications_and_concurrent_pushes_are_noops() -> None:
    event = make_event()
    publish(event)
    publish(event)
    wait_until(lambda: proxy_status(AUDIT_PROXY, event["event_id"])["deliveries"] >= 2)
    original = wait_for_audit(event["event_id"])

    def push() -> int:
        return httpx.post(
            f"{AUDIT_URL}/pubsub/push", json=push_wrapper(event), timeout=10
        ).status_code

    with ThreadPoolExecutor(max_workers=8) as executor:
        statuses = list(executor.map(lambda _: push(), range(8)))

    assert statuses == [204] * 8
    assert read_audit(event["event_id"]) == original


def test_concurrent_first_delivery_commits_one_audit_row() -> None:
    event = make_event()

    def push() -> int:
        return httpx.post(
            f"{AUDIT_URL}/pubsub/push", json=push_wrapper(event), timeout=10
        ).status_code

    with ThreadPoolExecutor(max_workers=8) as executor:
        statuses = list(executor.map(lambda _: push(), range(8)))

    assert statuses == [204] * 8
    assert len(read_audit(event["event_id"])) == 1


def test_audit_hash_conflict_and_distinct_events_for_same_item() -> None:
    original = make_event()
    response = httpx.post(
        f"{AUDIT_URL}/pubsub/push", json=push_wrapper(original), timeout=5
    )
    assert response.status_code == 204
    row = read_audit(original["event_id"])

    changed = {**original, "payload": {**original["payload"], "label": "Changed"}}
    response = httpx.post(
        f"{AUDIT_URL}/pubsub/push", json=push_wrapper(changed), timeout=5
    )
    assert response.status_code == 409
    assert read_audit(original["event_id"]) == row

    another = make_event(item_id=original["payload"]["item_id"], label="Another")
    response = httpx.post(
        f"{AUDIT_URL}/pubsub/push", json=push_wrapper(another), timeout=5
    )
    assert response.status_code == 204
    assert len(read_audit(another["event_id"])) == 1


def test_audit_post_commit_ack_loss_is_retried_without_another_row() -> None:
    event = make_event()
    response = httpx.post(
        f"{AUDIT_PROXY}/__test/lose-ack",
        json={"event_id": event["event_id"]},
        timeout=5,
    )
    response.raise_for_status()
    publish(event)
    wait_until(
        lambda: (
            proxy_status(AUDIT_PROXY, event["event_id"])["lost_acks"] == 1
            and proxy_status(AUDIT_PROXY, event["event_id"])["deliveries"] >= 2
        )
    )
    assert len(read_audit(event["event_id"])) == 1
    assert len(wait_for_projection(event)) == 1


def test_database_constraint_failure_does_not_commit_audit_row() -> None:
    event = make_event(item_id=secrets.token_urlsafe(8000))
    response = httpx.post(
        f"{AUDIT_URL}/pubsub/push", json=push_wrapper(event), timeout=10
    )
    assert response.status_code == 503
    assert read_audit(event["event_id"]) == []


def test_database_roles_enforce_append_only_and_cross_schema_isolation() -> None:
    event_id = uuid4()
    with audit_connection() as connection:
        connection.execute(
            "SELECT event_id, canonical_content_hash FROM audit_projection.audit_event LIMIT 1"
        )

    denied = (
        "UPDATE audit_projection.audit_event SET label = 'changed' WHERE event_id = %s",
        "DELETE FROM audit_projection.audit_event WHERE event_id = %s",
        "SELECT event_id FROM item_projection.processed_event WHERE event_id = %s",
    )
    for query in denied:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with audit_connection() as connection:
                connection.execute(query, (event_id,))

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with database_connection() as connection:
            connection.execute(
                "SELECT event_id FROM audit_projection.audit_event WHERE event_id = %s",
                (event_id,),
            )
