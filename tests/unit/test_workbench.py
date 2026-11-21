from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient

from robe_event_platform.database import DatabaseSettings
from robe_event_platform.workbench import api, observations


def test_invalid_cursor_is_rejected() -> None:
    client = TestClient(api.app)
    malformed = base64.urlsafe_b64encode(
        json.dumps(["2026-01-01T00:00:00+00:00", 123, "item", ["item", "audit"]]).encode()
    ).decode()
    assert client.get("/api/v1/observations", params={"cursor": malformed}).status_code == 400
    assert client.get("/api/v1/observations", params={"cursor": "not-base64!"}).status_code == 400


def test_partial_results_never_claim_missing_records(monkeypatch) -> None:
    config = DatabaseSettings("postgres", 5432, "demo", "workbench_reader", "test")
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    def failed(*_):
        raise psycopg.OperationalError("unavailable")

    monkeypatch.setattr(observations, "connect", lambda _: Connection())
    monkeypatch.setitem(observations.DETAIL_READERS, "item", lambda *_: None)
    monkeypatch.setitem(observations.DETAIL_READERS, "audit", failed)
    result = observations.event_detail(config, uuid4())
    assert result["sources"]["item"] == {"status": "not_observed", "record": None}
    assert result["sources"]["audit"] == {"status": "unknown", "record": None}

    row = {
        "recorded_at": datetime.now(timezone.utc),
        "event_id": uuid4(),
        "consumer": "item",
    }
    monkeypatch.setitem(observations.LIST_READERS, "item", lambda *_: [row, row])
    monkeypatch.setitem(observations.LIST_READERS, "audit", failed)
    result = observations.observations(config, ["item", "audit"], 1, None)
    assert result["sources"] == {"item": "available", "audit": "unknown"}
    assert result["next_cursor"] is None


def test_all_unavailable_is_a_service_error(monkeypatch) -> None:
    monkeypatch.setattr(api, "settings", lambda: None)
    monkeypatch.setattr(
        api, "event_detail",
        lambda *_: {"sources": {"item": {"status": "unknown"}, "audit": {"status": "unknown"}}},
    )
    assert TestClient(api.app).get(f"/api/v1/events/{uuid4()}").status_code == 503
