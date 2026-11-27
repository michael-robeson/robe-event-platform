from __future__ import annotations

import json
from concurrent.futures import Future
from copy import deepcopy
from urllib.error import URLError

import pytest
from fastapi.testclient import TestClient

from robe_event_platform.workbench import api, synthetic, topology

ORIGIN = "http://service:8000"
TOPIC = "projects/robe-local/topics/requests"
SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["event_id", "correlation_id", "payload"],
    "properties": {
        "event_id": {"type": "string", "format": "uuid"},
        "correlation_id": {"type": "string", "minLength": 1},
        "payload": {
            "type": "object",
            "required": ["value"],
            "properties": {"value": {"type": "string", "minLength": 1}},
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}
MESSAGE = {
    "event_id": "f83d2df4-5b13-467c-8a38-a7d4a870f587",
    "correlation_id": "correlation-1",
    "payload": {"value": "synthetic"},
}
DESCRIPTOR = {
    "schema_version": 1,
    "service": {"id": "sample", "name": "Sample", "description": "Sample service"},
    "health": {"path": "/healthz"},
    "messaging": {
        "provider": "google-cloud-pubsub",
        "project_id": "robe-local",
        "topics": [{"id": "requests", "name": "Requests", "role": "consumes"}],
        "subscriptions": [],
        "synthetic_templates": [{
            "id": "request", "name": "Request", "topic_id": "requests",
            "template_path": "/template", "contract_path": "/contract",
        }],
    },
}


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("WORKBENCH_SYNTHETIC_PUBLISH_ENABLED", "true")
    monkeypatch.setenv("PUBSUB_EMULATOR_HOST", "pubsub:8085")
    monkeypatch.setenv("PUBSUB_PROJECT_ID", "robe-local")
    monkeypatch.setattr(topology, "_service_urls", lambda: [ORIGIN])
    monkeypatch.setattr(api, "_discover_topics", lambda _: {
        "status": "available", "resources": [{"name": TOPIC}],
    })
    documents = {
        f"{ORIGIN}{topology.DESCRIPTOR_PATH}": DESCRIPTOR,
        f"{ORIGIN}/template": MESSAGE,
        f"{ORIGIN}/contract": SCHEMA,
    }
    monkeypatch.setattr(topology, "_read_json", lambda url: deepcopy(documents[url]))
    return TestClient(api.app, base_url="http://127.0.0.1:8083")


def request_body(message=None):
    return {
        "origin": ORIGIN, "template_id": "request", "topic": TOPIC,
        "message": deepcopy(MESSAGE if message is None else message),
    }


def post(client, body, **kwargs):
    return client.post(
        "/api/v1/synthetic/publish", json=body,
        headers={"X-Workbench-Intent": "synthetic-publication", **kwargs},
    )


def test_template_discovery_and_preview_do_not_publish(configured, monkeypatch):
    monkeypatch.setattr(synthetic.pubsub_v1, "PublisherClient", lambda: pytest.fail("unexpected publication"))
    listing = configured.get("/api/v1/synthetic/templates", params={"topic": TOPIC})
    preview = configured.get("/api/v1/synthetic/template", params={
        "topic": TOPIC, "origin": ORIGIN, "template_id": "request",
    })
    assert listing.json()["templates"] == [{
        "id": "request", "name": "Request", "origin": ORIGIN, "service": "Sample",
    }]
    assert preview.json() == MESSAGE


def test_publish_validates_and_preserves_identity(configured, monkeypatch):
    calls = []

    class Publisher:
        transport = None

        def __init__(self):
            self.transport = self

        def publish(self, topic, data, **kwargs):
            calls.append((topic, json.loads(data), kwargs))
            result = Future()
            result.set_result("broker-message-1")
            return result

        def close(self):
            pass

    monkeypatch.setattr(synthetic.pubsub_v1, "PublisherClient", Publisher)
    edited = deepcopy(MESSAGE)
    edited["payload"]["value"] = "edited"
    response = post(configured, request_body(edited))
    assert response.status_code == 200
    assert calls == [(TOPIC, edited, {"retry": None, "timeout": 5})]
    assert response.json() == {
        "status": "broker_accepted", "topic": TOPIC, "message_id": "broker-message-1",
        "event_id": edited["event_id"], "correlation_id": "correlation-1", "causation_id": None,
    }


def test_rejects_invalid_payload_format_and_external_contract_reference(configured, monkeypatch):
    monkeypatch.setattr(synthetic.pubsub_v1, "PublisherClient", lambda: pytest.fail("unexpected publication"))
    invalid = deepcopy(MESSAGE)
    invalid["event_id"] = "not-a-uuid"
    assert post(configured, request_body(invalid)).status_code == 422
    invalid = deepcopy(MESSAGE)
    invalid["payload"]["value"] = ""
    assert post(configured, request_body(invalid)).status_code == 422
    remote = {**SCHEMA, "$ref": "https://example.test/untrusted"}
    original = topology._read_json
    monkeypatch.setattr(topology, "_read_json", lambda url: remote if url.endswith("/contract") else original(url))
    assert post(configured, request_body()).status_code == 502


def test_local_schema_reference_and_invalid_service_template(configured, monkeypatch):
    local = {**deepcopy(SCHEMA), "$defs": {"value": {"type": "string", "minLength": 1}}}
    local["properties"]["payload"]["properties"]["value"] = {"$ref": "#/$defs/value"}
    original = topology._read_json
    monkeypatch.setattr(topology, "_read_json", lambda url: local if url.endswith("/contract") else original(url))
    preview = configured.get("/api/v1/synthetic/template", params={
        "topic": TOPIC, "origin": ORIGIN, "template_id": "request",
    })
    assert preview.status_code == 200
    invalid = deepcopy(MESSAGE)
    invalid["payload"]["value"] = ""
    monkeypatch.setattr(topology, "_read_json", lambda url: invalid if url.endswith("/template") else (
        local if url.endswith("/contract") else original(url)
    ))
    assert configured.get("/api/v1/synthetic/template", params={
        "topic": TOPIC, "origin": ORIGIN, "template_id": "request",
    }).status_code == 502


def test_unavailable_provider_and_inventory_are_explicit(configured, monkeypatch):
    def unavailable(_):
        raise URLError("unavailable")

    monkeypatch.setattr(topology, "_read_json", unavailable)
    listing = configured.get("/api/v1/synthetic/templates", params={"topic": TOPIC})
    assert listing.json() == {"templates": [], "errors": [f"Templates unavailable from {ORIGIN}"]}
    assert post(configured, request_body()).status_code == 503
    monkeypatch.setattr(api, "_discover_topics", lambda _: {"status": "unknown", "resources": []})
    assert post(configured, request_body()).status_code == 503


def test_rejects_disabled_nonlocal_unobserved_and_untrusted_requests(configured, monkeypatch):
    monkeypatch.setattr(synthetic.pubsub_v1, "PublisherClient", lambda: pytest.fail("unexpected publication"))
    monkeypatch.setenv("WORKBENCH_SYNTHETIC_PUBLISH_ENABLED", "false")
    assert post(configured, request_body()).status_code == 403
    monkeypatch.setenv("WORKBENCH_SYNTHETIC_PUBLISH_ENABLED", "true")
    monkeypatch.setenv("PUBSUB_EMULATOR_HOST", "remote:8085")
    assert post(configured, request_body()).status_code == 503
    monkeypatch.setenv("PUBSUB_EMULATOR_HOST", "pubsub:8085")
    assert post(configured, request_body(), Origin="http://evil.test").status_code == 403
    assert configured.post("/api/v1/synthetic/publish", json=request_body()).status_code == 403
    assert post(configured, {**request_body(), "topic": "projects/robe-local/topics/other"}).status_code == 404
    assert post(configured, {**request_body(), "origin": "http://unconfigured:8000"}).status_code == 404
    assert post(configured, {**request_body(), "template_id": "other"}).status_code == 404
    assert post(configured, request_body(), Host="service:8000").status_code == 403


def test_rejects_invalid_or_oversized_request_before_publication(configured, monkeypatch):
    monkeypatch.setattr(synthetic.pubsub_v1, "PublisherClient", lambda: pytest.fail("unexpected publication"))
    headers = {"X-Workbench-Intent": "synthetic-publication", "Content-Type": "application/json"}
    assert configured.post("/api/v1/synthetic/publish", content=b'{"message":NaN}', headers=headers).status_code == 400
    assert configured.post("/api/v1/synthetic/publish", content=b"x" * (synthetic.MESSAGE_LIMIT + 1), headers=headers).status_code == 413


def test_timeout_reports_unknown_acceptance(configured, monkeypatch):
    class TimedOut:
        def result(self, timeout):
            raise TimeoutError()

    class Publisher:
        transport = None

        def __init__(self):
            self.transport = self

        def publish(self, *_args, **_kwargs):
            return TimedOut()

        def close(self):
            pass

    monkeypatch.setattr(synthetic.pubsub_v1, "PublisherClient", Publisher)
    response = post(configured, request_body())
    assert response.status_code == 504
    assert "acceptance is unknown" in response.json()["detail"]
