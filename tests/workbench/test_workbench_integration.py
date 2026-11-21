from __future__ import annotations

import os
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest

from tests.e2e.test_vertical_slice import make_event, publish, wait_until
from tests.e2e.test_audit_consumer import admin_connection
from robe_event_platform.workbench.observations import encode_cursor

URL = "http://127.0.0.1:8083"


def test_status_ui_and_independent_event_inspection() -> None:
    root = httpx.get(URL, timeout=5)
    assert root.status_code == 200 and "Event Platform Workbench" in root.text
    assert root.headers["cache-control"] == "no-store"
    assert httpx.get(URL, headers={"Host": "unexpected.example"}, timeout=5).status_code == 400
    status = httpx.get(f"{URL}/api/v1/status", timeout=15)
    status.raise_for_status()
    data = status.json()
    assert all(value["status"] == "available" for value in data["services"].values())
    assert data["database"]["status"] == "available"
    assert all(value["status"] == "available" for value in data["emulator_resources"].values())

    missing = httpx.get(f"{URL}/api/v1/events/{uuid4()}", timeout=5).json()
    assert {item["status"] for item in missing["sources"].values()} == {"not_observed"}

    event = make_event()
    publish(event)

    def both_observed() -> bool:
        response = httpx.get(f"{URL}/api/v1/events/{event['event_id']}", timeout=5)
        response.raise_for_status()
        return all(source["status"] == "record_observed" for source in response.json()["sources"].values())

    wait_until(both_observed)
    detail = httpx.get(f"{URL}/api/v1/events/{event['event_id']}", timeout=5).json()
    assert detail["sources"]["item"]["record"]["projection"]["label"] == event["payload"]["label"]
    assert detail["sources"]["audit"]["record"]["item_id"] == event["payload"]["item_id"]
    assert detail["sources"]["audit"]["record"]["content_hash"] == detail["sources"]["item"]["record"]["ledger"]["content_hash"]

    first = httpx.get(f"{URL}/api/v1/observations", params={"limit": 1}, timeout=5).json()
    assert first["next_cursor"]
    second = httpx.get(
        f"{URL}/api/v1/observations", params={"limit": 1, "cursor": first["next_cursor"]}, timeout=5,
    ).json()
    assert first["observations"][0] != second["observations"][0]
    assert httpx.post(f"{URL}/api/v1/observations", timeout=5).status_code == 405


def test_item_projection_without_ledger_is_still_observed() -> None:
    event_id = uuid4()
    password = os.environ.get("ITEM_PROJECTION_DB_PASSWORD")
    if not password:
        raise RuntimeError("ITEM_PROJECTION_DB_PASSWORD is required")
    with psycopg.connect(
        host="127.0.0.1", port=55432, dbname="robe_events",
        user="item_projection_app", password=password,
    ) as connection:
        connection.execute(
            """
            INSERT INTO item_projection.item_projection
                (source, item_id, label, registered_event_id)
            VALUES ('workbench-test', %s, 'orphan projection', %s)
            """,
            (str(uuid4()), event_id),
        )
    response = httpx.get(f"{URL}/api/v1/events/{event_id}", timeout=5)
    response.raise_for_status()
    item = response.json()["sources"]["item"]
    assert item["status"] == "record_observed"
    assert item["record"]["ledger"] is None
    assert item["record"]["projection"]["label"] == "orphan projection"


def test_pagination_handles_same_event_and_transaction_time() -> None:
    event_id = uuid4()
    with admin_connection() as connection:
        inserted = connection.execute(
            """
            INSERT INTO item_projection.processed_event
                (event_id, event_type, contract_version, occurred_at, source, canonical_content_hash)
            VALUES (%s, 'demo.item.registered', '1', CURRENT_TIMESTAMP, 'workbench-test', %s)
            RETURNING processed_at
            """, (event_id, bytes(32)),
        ).fetchone()
        connection.execute(
            """
            INSERT INTO audit_projection.audit_event
                (event_id, event_type, contract_version, occurred_at, source, item_id, label, canonical_content_hash)
            VALUES (%s, 'demo.item.registered', '1', CURRENT_TIMESTAMP, 'workbench-test', 'item', 'label', %s)
            """, (event_id, bytes(32)),
        )
    assert inserted is not None
    cursor = encode_cursor(
        {"recorded_at": inserted[0], "event_id": UUID(int=(1 << 128) - 1), "consumer": "item"},
        ["item", "audit"],
    )
    first = httpx.get(
        f"{URL}/api/v1/observations", params={"limit": 1, "cursor": cursor}, timeout=5,
    ).json()
    second = httpx.get(
        f"{URL}/api/v1/observations", params={"limit": 1, "cursor": first["next_cursor"]}, timeout=5,
    ).json()
    assert first["observations"][0]["event_id"] == str(event_id)
    assert second["observations"][0]["event_id"] == str(event_id)
    assert {first["observations"][0]["consumer"], second["observations"][0]["consumer"]} == {"item", "audit"}


@pytest.mark.parametrize("table", [
    "item_projection.processed_event", "item_projection.item_projection",
    "audit_projection.audit_event",
])
def test_reader_cannot_modify_consumer_tables(table: str) -> None:
    password = os.environ.get("WORKBENCH_DB_PASSWORD")
    if not password:
        raise RuntimeError("WORKBENCH_DB_PASSWORD is required")
    with psycopg.connect(
        host="127.0.0.1", port=55432, dbname="robe_events",
        user="workbench_reader", password=password, autocommit=True,
    ) as connection:
        connection.execute("SET default_transaction_read_only = off")
        for statement in (
            f"DELETE FROM {table} WHERE false",
            f"UPDATE {table} SET source = source WHERE false",
            f"INSERT INTO {table} SELECT * FROM {table} WHERE false",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                connection.execute(statement)
        assert connection.execute(
            "SELECT has_table_privilege(current_user, %s, 'TRUNCATE')", (table,),
        ).fetchone() == (False,)
