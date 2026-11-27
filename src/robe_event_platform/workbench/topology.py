from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from robe_event_platform.local_config import LOCAL_PROJECT_ID

logger = logging.getLogger(__name__)
DESCRIPTOR_PATH = "/.well-known/robe-service.json"
DESCRIPTOR_LIMIT = 64 * 1024


class _SameOriginRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _same_origin(req.full_url, newurl):
            raise ValueError("redirect outside the configured service origin")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open_service(request: Request):
    return build_opener(_SameOriginRedirectHandler()).open(request, timeout=2)


def _service_urls() -> list[str]:
    try:
        value = json.loads(os.environ.get("WORKBENCH_SERVICE_URLS", "[]"))
    except json.JSONDecodeError as error:
        raise RuntimeError("WORKBENCH_SERVICE_URLS must be a JSON array") from error
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeError("WORKBENCH_SERVICE_URLS must be a JSON array of URLs")
    for item in value:
        parsed = urlsplit(item)
        if (
            parsed.scheme != "http"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise RuntimeError("Workbench service URLs must be plain HTTP origins without credentials")
    return [item.rstrip("/") for item in value]


def _read_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json"})
    with _open_service(request) as response:
        if response.status != 200:
            raise ValueError(f"HTTP {response.status}")
        if not _same_origin(url, response.geturl()):
            raise ValueError("descriptor redirected outside its configured origin")
        raw = response.read(DESCRIPTOR_LIMIT + 1)
    if len(raw) > DESCRIPTOR_LIMIT:
        raise ValueError("descriptor exceeds the size limit")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("descriptor must be a JSON object")
    return value


def _same_origin(first: str, second: str) -> bool:
    left = urlsplit(first)
    right = urlsplit(second)
    return (
        left.scheme == right.scheme
        and left.hostname == right.hostname
        and left.port == right.port
    )


def _relative_path(value: Any) -> str:
    if not isinstance(value, str) or not value.startswith("/") or value.startswith("//"):
        raise ValueError("endpoint must be a local absolute path")
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or ".." in parsed.path.split("/"):
        raise ValueError("endpoint must be a local absolute path")
    return value


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _validate_descriptor(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("schema_version") != 1:
        raise ValueError("unsupported descriptor schema_version")
    service = value.get("service")
    health = value.get("health")
    messaging = value.get("messaging")
    if not isinstance(service, dict) or not isinstance(health, dict) or not isinstance(messaging, dict):
        raise ValueError("descriptor is missing service, health, or messaging")
    for field in ("id", "name", "description"):
        _nonempty(service.get(field), f"service.{field}")
    health_path = _relative_path(health.get("path"))
    if messaging.get("provider") != "google-cloud-pubsub":
        raise ValueError("messaging.provider is unsupported")
    project_id = _nonempty(messaging.get("project_id"), "messaging.project_id")
    if "/" in project_id:
        raise ValueError("messaging.project_id is invalid")

    topics = messaging.get("topics")
    subscriptions = messaging.get("subscriptions")
    if not isinstance(topics, list) or not isinstance(subscriptions, list):
        raise ValueError("messaging topics and subscriptions must be arrays")
    for topic in topics:
        if not isinstance(topic, dict):
            raise ValueError("topic declarations must be objects")
        topic_id = _nonempty(topic.get("id"), "topic.id")
        _nonempty(topic.get("name"), "topic.name")
        if "/" in topic_id:
            raise ValueError("topic ids must be resource ids")
        role = topic.get("role")
        if not isinstance(role, str) or role not in {"publishes", "consumes", "dead_letter"}:
            raise ValueError("topic.role is unsupported")

    subscription_ids: set[str] = set()
    for subscription in subscriptions:
        if not isinstance(subscription, dict):
            raise ValueError("subscription declarations must be objects")
        subscription_id = _nonempty(subscription.get("id"), "subscription.id")
        _nonempty(subscription.get("name"), "subscription.name")
        if "/" in subscription_id or subscription_id in subscription_ids:
            raise ValueError("subscription ids must be unique resource ids")
        topic_id = _nonempty(subscription.get("topic_id"), "subscription.topic_id")
        if "/" in topic_id:
            raise ValueError("subscription.topic_id must be a resource id")
        delivery = subscription.get("delivery")
        if delivery == "push":
            _relative_path(subscription.get("endpoint"))
        elif delivery == "pull":
            if "endpoint" in subscription:
                raise ValueError("pull subscriptions must not declare an endpoint")
        else:
            raise ValueError("subscription.delivery is unsupported")
        subscription_ids.add(subscription_id)

    return {
        **value,
        "health": {"path": health_path},
    }


def _service_snapshot(base_url: str, index: int) -> dict[str, Any]:
    try:
        descriptor = _validate_descriptor(_read_json(f"{base_url}{DESCRIPTOR_PATH}"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeError, json.JSONDecodeError) as error:
        logger.warning("Workbench descriptor unavailable for %s: %s", base_url, error)
        return {
            "id": f"configured-{index + 1}",
            "name": f"Configured service {index + 1}",
            "url": base_url,
            "descriptor_status": "unknown",
            "error": f"Descriptor unavailable: {error}",
            "health_status": "unknown",
            "descriptor": None,
        }

    health_url = f"{base_url}{descriptor['health']['path']}"
    try:
        request = Request(health_url, method="GET")
        with _open_service(request) as response:
            if not _same_origin(health_url, response.geturl()):
                raise ValueError("health check redirected outside its configured origin")
            health_status = "available" if response.status == 200 else "unknown"
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        logger.warning("Workbench health endpoint unavailable for %s: %s", base_url, error)
        health_status = "unknown"
        health_error = f"Health check unavailable: {error}"
    else:
        health_error = None

    service = descriptor["service"]
    return {
        "id": service["id"],
        "name": service["name"],
        "url": base_url,
        "descriptor_status": "available",
        "error": None,
        "health_status": health_status,
        "health_error": health_error,
        "health_url": health_url,
        "descriptor": descriptor,
    }


def _resource_id(kind: str, project_id: str, resource_id: str) -> str:
    return f"projects/{project_id}/{kind}/{resource_id}"


def _edge(
    edges: dict[tuple[str, str, str], dict[str, Any]],
    source: str,
    target: str,
    relationship: str,
    evidence: str,
    status: str = "available",
) -> None:
    key = (source, target, relationship)
    edge = edges.setdefault(
        key,
        {
            "id": f"{source}|{relationship}|{target}",
            "source": source,
            "target": target,
            "relationship": relationship,
            "evidence": [],
            "status": status,
        },
    )
    if evidence not in edge["evidence"]:
        edge["evidence"].append(evidence)
    if status != "available":
        edge["status"] = status


def build_topology(
    inventory: dict[str, Any],
    service_urls: list[str] | None = None,
) -> dict[str, Any]:
    configured_urls = _service_urls() if service_urls is None else service_urls
    snapshots = [_service_snapshot(url, index) for index, url in enumerate(configured_urls)]
    observed_topics = {
        item["name"]: item
        for item in inventory["topics"].get("resources", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    observed_subscriptions = {
        item["name"]: item
        for item in inventory["subscriptions"].get("resources", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    declared_topics: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    subscription_topics: dict[str, set[str]] = {}
    declared_subscriptions: dict[str, list[tuple[str, dict[str, Any], str]]] = {}
    topic_project_ids: dict[str, str] = {}

    topics_status = inventory["topics"].get("status", "unknown")
    subscriptions_status = inventory["subscriptions"].get("status", "unknown")
    nodes["infrastructure:pubsub-emulator"] = {
        "id": "infrastructure:pubsub-emulator",
        "kind": "infrastructure",
        "name": "Pub/Sub emulator",
        "status": "available" if topics_status == subscriptions_status == "available" else "unknown",
        "declared": False,
        "observed": topics_status == subscriptions_status == "available",
        "details": {
            "provider": "Google Cloud Pub/Sub emulator",
            "topics_status": topics_status,
            "subscriptions_status": subscriptions_status,
            "topics_error": inventory["topics"].get("error"),
            "subscriptions_error": inventory["subscriptions"].get("error"),
        },
    }

    for snapshot in snapshots:
        descriptor = snapshot["descriptor"]
        service_node_id = f"service:{snapshot['id']}"
        if service_node_id in nodes:
            service_node_id = f"{service_node_id}:{len(nodes)}"
        nodes[service_node_id] = {
            "id": service_node_id,
            "kind": "service",
            "name": snapshot["name"],
            "status": snapshot["health_status"],
            "declared": descriptor is not None,
            "observed": snapshot["health_status"] == "available",
            "details": {
                "service_id": snapshot["id"],
                "base_url": snapshot["url"],
                "descriptor_status": snapshot["descriptor_status"],
                "descriptor_error": snapshot["error"],
                "health_status": snapshot["health_status"],
                "health_url": snapshot.get("health_url"),
                "health_error": snapshot.get("health_error"),
                "description": descriptor["service"]["description"] if descriptor else None,
            },
        }
        if descriptor is None:
            continue

        messaging = descriptor["messaging"]
        project_id = messaging["project_id"]
        for topic in messaging["topics"]:
            name = _resource_id("topics", project_id, topic["id"])
            topic_project_ids[name] = project_id
            declared_topics.setdefault(name, []).append((service_node_id, topic))
            _edge(
                edges,
                service_node_id,
                f"topic:{name}",
                topic["role"],
                "declared",
            )
        for subscription in messaging["subscriptions"]:
            name = _resource_id("subscriptions", project_id, subscription["id"])
            declared_subscriptions.setdefault(name, []).append(
                (service_node_id, subscription, project_id)
            )
            topic_name = _resource_id("topics", project_id, subscription["topic_id"])
            topic_project_ids[topic_name] = project_id
            subscription_topics.setdefault(topic_name, set()).add(service_node_id)

    referenced_topics = {
        item.get("topic")
        for item in observed_subscriptions.values()
        if isinstance(item.get("topic"), str)
    }
    referenced_topics.update(
        policy["topic"]
        for item in observed_subscriptions.values()
        if isinstance((policy := item.get("dead_letter_policy")), dict)
        and isinstance(policy.get("topic"), str)
        and policy["topic"]
    )
    all_topic_names = set(observed_topics) | set(declared_topics) | set(subscription_topics) | referenced_topics
    for name in sorted(all_topic_names):
        declarations = declared_topics.get(name, [])
        declarers = {service_id for service_id, _ in declarations} | subscription_topics.get(name, set())
        observed = observed_topics.get(name)
        declared_projects = {topic_project_ids[name]} if name in topic_project_ids else set()
        project_mismatch = any(project_id != LOCAL_PROJECT_ID for project_id in declared_projects)
        status = (
            "available" if observed
            else "unknown"
            if topics_status != "available" or project_mismatch or name in referenced_topics
            else "not_found"
        )
        short_name = name.rsplit("/", 1)[-1]
        nodes[f"topic:{name}"] = {
            "id": f"topic:{name}",
            "kind": "topic",
            "name": declarations[0][1]["name"] if declarations else short_name,
            "status": status,
            "declared": bool(declarers),
            "observed": observed is not None,
            "details": {
                "resource_name": name,
                "role": ", ".join(sorted({topic["role"] for _, topic in declarations})) or None,
                "declared_by": sorted({nodes[service_id]["details"]["service_id"] for service_id in declarers}),
                "configuration": observed,
                "discovery_status": topics_status,
            },
        }

    all_subscription_names = set(observed_subscriptions) | set(declared_subscriptions)
    for name in sorted(all_subscription_names):
        declarations = declared_subscriptions.get(name, [])
        observed = observed_subscriptions.get(name)
        declared_project = declarations[0][2] if declarations else None
        observed_topic = observed.get("topic") if observed else None
        project_mismatch = bool(declared_project and declared_project != LOCAL_PROJECT_ID)
        status = (
            "available" if observed
            else "unknown" if subscriptions_status != "available" or project_mismatch
            else "not_found"
        )
        topic_name = observed_topic
        for service_id, subscription, project_id in declarations:
            declared_topic = _resource_id("topics", project_id, subscription["topic_id"])
            topic_name = topic_name or declared_topic
            relationship_status = (
                "unknown" if subscriptions_status != "available"
                else "not_found" if observed is None
                else "mismatch" if observed_topic != declared_topic
                else "available"
            )
            _edge(
                edges,
                f"topic:{declared_topic}",
                f"subscription:{name}",
                "delivers_to",
                "declared",
                relationship_status,
            )
            if observed_topic == declared_topic:
                _edge(
                    edges,
                    f"topic:{declared_topic}",
                    f"subscription:{name}",
                    "delivers_to",
                    "observed",
                )
            if subscription["delivery"] == "push":
                expected_endpoint = (
                    nodes[service_id]["details"]["base_url"] + subscription["endpoint"]
                )
                observed_endpoint = observed.get("push_endpoint") if observed else None
                endpoint_status = (
                    "not_found" if observed is None and subscriptions_status == "available"
                    else "unknown" if observed is None or subscriptions_status != "available"
                    else "available" if observed_endpoint == expected_endpoint
                    else "mismatch" if observed_endpoint is not None
                    else "mismatch"
                )
                _edge(
                    edges,
                    f"subscription:{name}",
                    service_id,
                    "pushes_to",
                    "declared",
                    endpoint_status,
                )
                if observed_endpoint == expected_endpoint:
                    _edge(
                        edges,
                        f"subscription:{name}",
                        service_id,
                        "pushes_to",
                        "observed",
                    )
        if observed and observed_topic:
            _edge(
                edges,
                f"topic:{observed_topic}",
                f"subscription:{name}",
                "delivers_to",
                "observed",
            )
        if observed:
            policy = observed.get("dead_letter_policy")
            if isinstance(policy, dict) and isinstance(policy.get("topic"), str) and policy["topic"]:
                _edge(
                    edges,
                    f"subscription:{name}",
                    f"topic:{policy['topic']}",
                    "dead_letter_policy",
                    "observed",
                )
        nodes[f"subscription:{name}"] = {
            "id": f"subscription:{name}",
            "kind": "subscription",
            "name": declarations[0][1]["name"] if declarations else name.rsplit("/", 1)[-1],
            "status": status,
            "declared": bool(declarations),
            "observed": observed is not None,
            "details": {
                "resource_name": name,
                "topic": topic_name,
                "delivery": declarations[0][1]["delivery"] if declarations else (
                    "push" if observed and observed.get("push_endpoint") else "pull"
                ),
                "declared_by": [nodes[service_id]["details"]["service_id"] for service_id, _, _ in declarations],
                "configuration": observed,
                "discovery_status": subscriptions_status,
            },
        }

    for node in nodes.values():
        if node["kind"] in {"topic", "subscription"}:
            _edge(
                edges,
                "infrastructure:pubsub-emulator",
                node["id"],
                "contains",
                "observed" if node["observed"] else "declared",
            )

    return {
        "checked_at": datetime.now(timezone.utc),
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
    }
