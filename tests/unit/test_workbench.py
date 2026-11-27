from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from google.api_core.exceptions import ServiceUnavailable
from fastapi.testclient import TestClient

from robe_event_platform.database import DatabaseSettings
from robe_event_platform.workbench import api, observations


def test_push_endpoint_details_omit_userinfo_and_query_parameters() -> None:
    assert api._safe_push_endpoint(
        "https://user:secret@example.test/push?token=private"
    ) == "https://example.test/push"


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


def test_pubsub_inventory_lists_all_resources_and_reported_relationships(monkeypatch) -> None:
    monkeypatch.setattr(
        api, "require_local_pubsub", lambda: (api.LOCAL_EMULATOR_HOST, api.LOCAL_PROJECT_ID),
    )
    topics = [
        SimpleNamespace(name="projects/robe-local/topics/topic-a"),
        SimpleNamespace(name="projects/robe-local/topics/topic-b"),
    ]
    subscriptions = [
        SimpleNamespace(
            name="projects/robe-local/subscriptions/sub-a",
            topic="projects/robe-local/topics/topic-a",
        ),
        SimpleNamespace(
            name="projects/robe-local/subscriptions/sub-b",
            topic="projects/robe-local/topics/topic-a",
        ),
    ]

    class Publisher:
        transport = SimpleNamespace(close=lambda: None)

        def list_topics(self, **_):
            return iter(topics)

    class Subscriber:
        transport = SimpleNamespace(close=lambda: None)

        def list_subscriptions(self, **_):
            return iter(subscriptions)

    monkeypatch.setattr(api.pubsub_v1, "PublisherClient", Publisher)
    monkeypatch.setattr(api.pubsub_v1, "SubscriberClient", Subscriber)
    response = TestClient(api.app).get("/api/v1/pubsub/resources")

    assert response.status_code == 200
    assert response.json() == {
        "topics": {"status": "available", "resources": [
            {"name": "projects/robe-local/topics/topic-a"},
            {"name": "projects/robe-local/topics/topic-b"},
        ]},
        "subscriptions": {"status": "available", "resources": [
            {
                "name": "projects/robe-local/subscriptions/sub-a",
                "topic": "projects/robe-local/topics/topic-a",
            },
            {
                "name": "projects/robe-local/subscriptions/sub-b",
                "topic": "projects/robe-local/topics/topic-a",
            },
        ]},
    }


def test_pubsub_inventory_distinguishes_empty_from_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        api, "require_local_pubsub", lambda: (api.LOCAL_EMULATOR_HOST, api.LOCAL_PROJECT_ID),
    )

    class EmptyPublisher:
        transport = SimpleNamespace(close=lambda: None)

        def list_topics(self, **_):
            return iter(())

    class FailedSubscriber:
        transport = SimpleNamespace(close=lambda: None)

        def list_subscriptions(self, **_):
            raise ServiceUnavailable("emulator unavailable")

    monkeypatch.setattr(api.pubsub_v1, "PublisherClient", EmptyPublisher)
    monkeypatch.setattr(api.pubsub_v1, "SubscriberClient", FailedSubscriber)
    response = TestClient(api.app).get("/api/v1/pubsub/resources")

    assert response.json() == {
        "topics": {"status": "available", "resources": []},
        "subscriptions": {
            "status": "unknown",
            "resources": [],
            "error": "Subscription discovery unavailable",
        },
    }


def test_pubsub_inventory_marks_partial_pagination_failure_unknown(monkeypatch) -> None:
    monkeypatch.setattr(
        api, "require_local_pubsub", lambda: (api.LOCAL_EMULATOR_HOST, api.LOCAL_PROJECT_ID),
    )

    class PartialPublisher:
        transport = SimpleNamespace(close=lambda: None)

        def list_topics(self, **_):
            def pages():
                yield SimpleNamespace(name="projects/robe-local/topics/first-page")
                raise ServiceUnavailable("next page unavailable")

            return pages()

    class EmptySubscriber:
        transport = SimpleNamespace(close=lambda: None)

        def list_subscriptions(self, **_):
            return iter(())

    monkeypatch.setattr(api.pubsub_v1, "PublisherClient", PartialPublisher)
    monkeypatch.setattr(api.pubsub_v1, "SubscriberClient", EmptySubscriber)
    response = TestClient(api.app).get("/api/v1/pubsub/resources")
    result = response.json()

    assert result["topics"] == {
        "status": "unknown",
        "resources": [{"name": "projects/robe-local/topics/first-page"}],
        "error": "Topic discovery unavailable",
    }
    assert result["subscriptions"] == {"status": "available", "resources": []}


def test_pubsub_inventory_never_uses_a_non_local_emulator(monkeypatch) -> None:
    monkeypatch.setattr(
        api, "require_local_pubsub", lambda: ("pubsub.example.com:8085", api.LOCAL_PROJECT_ID),
    )

    class UnexpectedClient:
        def __init__(self):
            raise AssertionError("Pub/Sub clients must not be created for a non-local host")

    monkeypatch.setattr(api.pubsub_v1, "PublisherClient", UnexpectedClient)
    monkeypatch.setattr(api.pubsub_v1, "SubscriberClient", UnexpectedClient)
    result = TestClient(api.app).get("/api/v1/pubsub/resources").json()

    assert result["topics"]["status"] == "unknown"
    assert result["subscriptions"]["status"] == "unknown"
