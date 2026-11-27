from __future__ import annotations

import json
from urllib.request import Request

import pytest

from fastapi.testclient import TestClient

from robe_event_platform.workbench import api, topology


def descriptor() -> dict:
    return {
        "schema_version": 1,
        "service": {
            "id": "sample-service",
            "name": "Sample service",
            "description": "A test service.",
        },
        "health": {"path": "/healthz"},
        "messaging": {
            "provider": "google-cloud-pubsub",
            "project_id": "robe-local",
            "topics": [
                {"id": "requests", "name": "Requests", "role": "consumes"},
                {"id": "events", "name": "Events", "role": "publishes"},
            ],
            "subscriptions": [
                {
                    "id": "sample-requests",
                    "name": "Sample requests",
                    "topic_id": "requests",
                    "delivery": "push",
                    "endpoint": "/push",
                }
            ],
        },
    }


def test_topology_separates_declared_relationships_resources_and_health(monkeypatch) -> None:
    url = "http://sample-service:8000"
    monkeypatch.setattr(api, "pubsub_resources", lambda: {
        "topics": {
            "status": "available",
            "resources": [
                {"name": "projects/robe-local/topics/requests"},
                {"name": "projects/robe-local/topics/events"},
                {"name": "projects/robe-local/topics/unclaimed"},
            ],
        },
        "subscriptions": {
            "status": "available",
            "resources": [
                {
                    "name": "projects/robe-local/subscriptions/sample-requests",
                    "topic": "projects/robe-local/topics/requests",
                    "push_endpoint": f"{url}/push",
                    "ack_deadline_seconds": 30,
                },
                {
                    "name": "projects/robe-local/subscriptions/unclaimed-sub",
                    "topic": "projects/robe-local/topics/unclaimed",
                },
            ],
        },
    })
    monkeypatch.setattr(topology, "_service_urls", lambda: [url])
    monkeypatch.setattr(topology, "_service_snapshot", lambda *_: {
        "id": "sample-service",
        "name": "Sample service",
        "url": url,
        "descriptor_status": "available",
        "error": None,
        "health_status": "unknown",
        "health_error": "Health check unavailable",
        "health_url": f"{url}/healthz",
        "descriptor": descriptor(),
    })

    result = TestClient(api.app).get("/api/v1/topology").json()

    nodes = {node["id"]: node for node in result["nodes"]}
    edges = {
        (edge["source"], edge["target"], edge["relationship"]): edge
        for edge in result["edges"]
    }
    service = nodes["service:sample-service"]
    assert service["status"] == "unknown"
    assert service["details"]["descriptor_status"] == "available"
    assert nodes["topic:projects/robe-local/topics/unclaimed"]["declared"] is False
    assert nodes["subscription:projects/robe-local/subscriptions/unclaimed-sub"]["observed"] is True
    assert nodes["subscription:projects/robe-local/subscriptions/sample-requests"]["details"][
        "configuration"
    ]["ack_deadline_seconds"] == 30
    assert edges[
        (
            "topic:projects/robe-local/topics/requests",
            "subscription:projects/robe-local/subscriptions/sample-requests",
            "delivers_to",
        )
    ]["evidence"] == ["declared", "observed"]
    assert edges[
        (
            "subscription:projects/robe-local/subscriptions/sample-requests",
            "service:sample-service",
            "pushes_to",
        )
    ]["evidence"] == ["declared", "observed"]


def test_descriptor_rejects_non_local_health_and_push_endpoints() -> None:
    value = descriptor()
    value["health"]["path"] = "https://example.test/health"

    try:
        topology._validate_descriptor(value)
    except ValueError as error:
        assert "local absolute path" in str(error)
    else:
        raise AssertionError("A remote health endpoint must be rejected.")

    value = descriptor()
    value["messaging"]["subscriptions"][0]["endpoint"] = "//example.test/push"
    try:
        topology._validate_descriptor(value)
    except ValueError as error:
        assert "local absolute path" in str(error)
    else:
        raise AssertionError("A network-relative push endpoint must be rejected.")


def test_service_snapshot_fetches_descriptor_and_probes_declared_health(monkeypatch) -> None:
    url = "http://sample-service:8000"

    class Response:
        def __init__(self, status: int, body: bytes, final_url: str):
            self.status = status
            self.body = body
            self.final_url = final_url

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, _limit: int) -> bytes:
            return self.body

        def geturl(self) -> str:
            return self.final_url

    def fake_open_service(request):
        if request.full_url.endswith(topology.DESCRIPTOR_PATH):
            return Response(200, json.dumps(descriptor()).encode(), request.full_url)
        assert request.full_url == f"{url}/healthz"
        return Response(200, b'{"status":"ok"}', request.full_url)

    monkeypatch.setattr(topology, "_open_service", fake_open_service)

    result = topology._service_snapshot(url, 0)

    assert result["descriptor_status"] == "available"
    assert result["health_status"] == "available"
    assert result["health_url"] == f"{url}/healthz"
    assert result["descriptor"]["service"]["id"] == "sample-service"


def test_service_redirect_is_rejected_before_leaving_configured_origin() -> None:
    handler = topology._SameOriginRedirectHandler()
    request = Request("http://sample-service:8000/.well-known/robe-service.json")
    with pytest.raises(ValueError, match="outside the configured service origin"):
        handler.redirect_request(request, None, 302, "Found", {}, "http://other-service:8000/healthz")
    same_origin = handler.redirect_request(request, None, 302, "Found", {}, "http://sample-service:8000/healthz")
    assert same_origin.full_url == "http://sample-service:8000/healthz"


def test_service_can_publish_and_consume_the_same_topic(monkeypatch) -> None:
    value = descriptor()
    value["messaging"]["topics"].append(
        {"id": "requests", "name": "Requests", "role": "publishes"}
    )
    validated = topology._validate_descriptor(value)
    monkeypatch.setattr(topology, "_service_snapshot", lambda url, _: {
        "id": "sample-service", "name": "Sample service", "url": url,
        "descriptor_status": "available", "error": None, "health_status": "available",
        "descriptor": validated,
    })
    result = topology.build_topology(
        {"topics": {"status": "available", "resources": []},
         "subscriptions": {"status": "available", "resources": []}},
        service_urls=["http://sample-service:8000"],
    )
    roles = {
        edge["relationship"] for edge in result["edges"]
        if edge["source"] == "service:sample-service"
        and edge["target"] == "topic:projects/robe-local/topics/requests"
    }
    assert roles == {"publishes", "consumes"}


def test_subscription_can_declare_a_topic_without_a_topic_role(monkeypatch) -> None:
    value = descriptor()
    value["messaging"]["topics"] = []
    validated = topology._validate_descriptor(value)
    monkeypatch.setattr(topology, "_service_snapshot", lambda url, _: {
        "id": "sample-service", "name": "Sample service", "url": url,
        "descriptor_status": "available", "error": None, "health_status": "available",
        "descriptor": validated,
    })
    result = topology.build_topology(
        {"topics": {"status": "available", "resources": []},
         "subscriptions": {"status": "available", "resources": []}},
        service_urls=["http://sample-service:8000"],
    )
    topic = next(node for node in result["nodes"] if node["id"] == "topic:projects/robe-local/topics/requests")
    assert topic["declared"] is True
    assert topic["status"] == "not_found"
    assert topic["details"]["role"] is None
    assert topic["details"]["declared_by"] == ["sample-service"]
    assert any(edge["source"] == topic["id"] and edge["relationship"] == "delivers_to"
               for edge in result["edges"])


def test_dead_letter_policy_is_observed_from_subscription_not_service() -> None:
    request_topic = "projects/robe-local/topics/requests"
    dead_topic = "projects/robe-local/topics/dead"
    subscription = "projects/robe-local/subscriptions/sample-requests"
    result = topology.build_topology(
        {
            "topics": {"status": "unknown", "resources": []},
            "subscriptions": {
                "status": "available",
                "resources": [{
                    "name": subscription,
                    "topic": request_topic,
                    "dead_letter_policy": {"topic": dead_topic, "max_delivery_attempts": 5},
                }],
            },
        },
        service_urls=[],
    )
    nodes = {node["id"]: node for node in result["nodes"]}
    assert nodes[f"topic:{dead_topic}"]["status"] == "unknown"
    assert nodes[f"topic:{dead_topic}"]["observed"] is False
    policy_edges = [edge for edge in result["edges"] if edge["relationship"] == "dead_letter_policy"]
    assert len(policy_edges) == 1
    assert policy_edges[0]["source"] == f"subscription:{subscription}"
    assert policy_edges[0]["target"] == f"topic:{dead_topic}"
    assert policy_edges[0]["evidence"] == ["observed"]
