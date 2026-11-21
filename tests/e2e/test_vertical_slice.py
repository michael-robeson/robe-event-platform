from __future__ import annotations

import base64
import json
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import psycopg

ROOT = Path(__file__).resolve().parents[2]
PUBLISHER_URL = os.environ.get("PUBLISHER_URL", "http://127.0.0.1:8080")
CONSUMER_URL = os.environ.get("CONSUMER_URL", "http://127.0.0.1:8081")
PROXY_URL = os.environ.get("PROXY_URL", "http://127.0.0.1:9001")
DB_PASSWORD = os.environ.get("ITEM_PROJECTION_DB_PASSWORD")
SOURCE = "vertical-slice-integration-tests"
SUBSCRIPTION = "projects/robe-local/subscriptions/demo-item-projection"
SUCCESS_STATUSES = {102, 200, 201, 202, 204}


def database_connection() -> psycopg.Connection[tuple]:
    if not DB_PASSWORD:
        raise RuntimeError(
            "Source .env before running end-to-end tests to set "
            "ITEM_PROJECTION_DB_PASSWORD"
        )
    return psycopg.connect(
        host="127.0.0.1",
        port=55432,
        dbname="robe_events",
        user="item_projection_app",
        password=DB_PASSWORD,
        autocommit=False,
    )


def make_event(
    *,
    event_id: UUID | None = None,
    item_id: str | None = None,
    label: str = "Example",
) -> dict[str, Any]:
    return {
        "event_id": str(event_id or uuid4()),
        "event_type": "demo.item.registered",
        "contract_version": "1",
        "occurred_at": "2026-11-20T12:00:00Z",
        "source": SOURCE,
        "payload": {
            "item_id": item_id or f"item-{uuid4()}",
            "label": label,
        },
    }


def push_wrapper(event: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode()
    return {
        "message": {
            "data": base64.b64encode(data).decode("ascii"),
            "messageId": f"direct-test-{uuid4()}",
            "publishTime": "2026-11-20T12:00:00Z",
            "attributes": {},
        },
        "subscription": SUBSCRIPTION,
    }


def publish(event: dict[str, Any]) -> str:
    response = httpx.post(f"{PUBLISHER_URL}/events", json=event, timeout=10)
    assert response.status_code == 202, response.text
    return response.json()["pubsub_message_id"]


def get_counts(event_id: str) -> dict[str, int]:
    response = httpx.get(f"{PROXY_URL}/__test/status/{event_id}", timeout=5)
    response.raise_for_status()
    return response.json()


def wait_until(
    condition: Callable[[], bool], *, timeout: float = 30, interval: float = 0.2
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(interval)
    raise AssertionError(f"Condition not met within {timeout} seconds")


def read_projection(source: str, item_id: str) -> list[tuple[Any, ...]]:
    with database_connection() as connection:
        return connection.execute(
            """
            SELECT source, item_id, label, registered_event_id
            FROM item_projection.item_projection
            WHERE source = %s AND item_id = %s
            """,
            (source, item_id),
        ).fetchall()


def read_ledger(event_id: UUID) -> list[tuple[Any, ...]]:
    with database_connection() as connection:
        return connection.execute(
            """
            SELECT event_id, canonical_content_hash
            FROM item_projection.processed_event
            WHERE event_id = %s
            """,
            (event_id,),
        ).fetchall()


def set_proxy_mode(endpoint: str) -> None:
    response = httpx.post(f"{PROXY_URL}/__test/{endpoint}", timeout=5)
    response.raise_for_status()


def wait_for_projection(event: dict[str, Any]) -> list[tuple[Any, ...]]:
    item_id = event["payload"]["item_id"]
    result: list[tuple[Any, ...]] = []

    def projection_exists() -> bool:
        nonlocal result
        result = read_projection(event["source"], item_id)
        return bool(result)

    wait_until(projection_exists, timeout=30)
    return result


def test_publisher_acceptance_precedes_consumer_persistence() -> None:
    event = make_event()
    event_id = event["event_id"]
    item_id = event["payload"]["item_id"]
    set_proxy_mode("hold")
    try:
        publish(event)
        wait_until(lambda: get_counts(event_id)["deliveries"] >= 1)
        assert read_ledger(UUID(event_id)) == []
        assert read_projection(SOURCE, item_id) == []
    finally:
        set_proxy_mode("release")

    projection = wait_for_projection(event)
    assert len(projection) == 1
    assert len(read_ledger(UUID(event_id))) == 1


def test_duplicate_publication_is_a_successful_noop() -> None:
    event = make_event()
    first_message_id = publish(event)
    second_message_id = publish(event)

    assert first_message_id != second_message_id
    projection = wait_for_projection(event)
    wait_until(lambda: get_counts(event["event_id"])["deliveries"] >= 2)

    assert len(projection) == 1
    assert len(read_ledger(UUID(event["event_id"]))) == 1


def test_reused_event_id_with_different_content_is_rejected() -> None:
    original = make_event()
    publish(original)
    wait_for_projection(original)
    original_hash = read_ledger(UUID(original["event_id"]))[0][1]

    conflict = {
        **original,
        "payload": {**original["payload"], "label": "Changed"},
    }
    response = httpx.post(
        f"{CONSUMER_URL}/pubsub/push",
        json=push_wrapper(conflict),
        timeout=5,
    )

    assert response.status_code == 409
    assert read_ledger(UUID(original["event_id"]))[0][1] == original_hash
    projection = read_projection(SOURCE, original["payload"]["item_id"])
    assert len(projection) == 1
    assert projection[0][2] == original["payload"]["label"]


def test_business_key_conflict_rolls_back_the_ledger_insert() -> None:
    original = make_event()
    publish(original)
    wait_for_projection(original)

    conflict = make_event(item_id=original["payload"]["item_id"], label="Changed")
    response = httpx.post(
        f"{CONSUMER_URL}/pubsub/push",
        json=push_wrapper(conflict),
        timeout=5,
    )

    assert response.status_code == 409
    assert read_ledger(UUID(conflict["event_id"])) == []
    projection = read_projection(SOURCE, original["payload"]["item_id"])
    assert len(projection) == 1
    assert projection[0][2] == original["payload"]["label"]


def test_database_failure_recovers_and_processes_once() -> None:
    event = make_event()
    event_id = event["event_id"]
    stopped = False
    subprocess.run(
        ["docker", "compose", "stop", "postgres"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    stopped = True
    try:
        publish(event)
        wait_until(lambda: get_counts(event_id)["non_successes"] >= 1)
    finally:
        if stopped:
            subprocess.run(
                ["docker", "compose", "start", "postgres"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

    def database_is_ready() -> bool:
        try:
            with database_connection() as connection:
                connection.execute("SELECT 1")
            return True
        except psycopg.OperationalError:
            return False

    wait_until(database_is_ready, timeout=30)
    projection = wait_for_projection(event)
    assert len(projection) == 1
    assert len(read_ledger(UUID(event_id))) == 1


def test_lost_post_commit_response_redelivers_without_second_write() -> None:
    event = make_event()
    response = httpx.post(
        f"{PROXY_URL}/__test/lose-ack",
        json={"event_id": event["event_id"]},
        timeout=5,
    )
    response.raise_for_status()

    publish(event)
    wait_until(
        lambda: (
            get_counts(event["event_id"])["lost_acks"] == 1
            and get_counts(event["event_id"])["deliveries"] >= 2
        )
    )
    projection = wait_for_projection(event)

    assert len(projection) == 1
    assert len(read_ledger(UUID(event["event_id"]))) == 1
