from __future__ import annotations

import json
import logging
from http.client import HTTPConnection, HTTPException as HTTPClientError
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

import psycopg
from fastapi import FastAPI, HTTPException, Query, Request
from google.api_core.exceptions import GoogleAPICallError, NotFound
from google.cloud import pubsub_v1
from starlette.concurrency import run_in_threadpool

from robe_event_platform.database import DatabaseSettings
from robe_event_platform.local_config import (
    AUDIT_SUBSCRIPTION_ID, EVENT_TOPIC_ID, LOCAL_EMULATOR_HOST, LOCAL_PROJECT_ID,
    PROJECTION_SUBSCRIPTION_ID, require_local_pubsub,
)
from robe_event_platform.workbench.observations import (
    connect, decode_cursor, event_detail, observations,
)
from robe_event_platform.workbench.topology import build_topology
from robe_event_platform.workbench import synthetic

logger = logging.getLogger(__name__)
app = FastAPI(title="Local Event Platform Workbench", docs_url=None, redoc_url=None)


def _safe_push_endpoint(value: str) -> str:
    try:
        parsed = urlsplit(value)
        if not parsed.scheme or not parsed.hostname:
            return "configured"
        host = parsed.hostname
        if ":" in host:
            host = f"[{host}]"
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"
        return urlunsplit((parsed.scheme, host, parsed.path, "", ""))
    except ValueError:
        return "configured"


def settings() -> DatabaseSettings:
    config = DatabaseSettings.from_environment()
    if config.user != "workbench_reader":
        raise RuntimeError("Workbench requires the dedicated workbench_reader role")
    return config


def http_liveness(host: str) -> str:
    try:
        connection = HTTPConnection(host, 8000, timeout=2)
        try:
            connection.request("GET", "/healthz")
            return "available" if connection.getresponse().status == 200 else "unknown"
        finally:
            connection.close()
    except (HTTPClientError, TimeoutError, OSError):
        return "unknown"


def emulator_status() -> dict[str, dict[str, str]]:
    names = {
        "topic": EVENT_TOPIC_ID,
        "item_subscription": PROJECTION_SUBSCRIPTION_ID,
        "audit_subscription": AUDIT_SUBSCRIPTION_ID,
    }
    results = {name: {"status": "unknown"} for name in names}
    try:
        host, project = require_local_pubsub()
        if host != LOCAL_EMULATOR_HOST or project != LOCAL_PROJECT_ID:
            raise RuntimeError("Workbench only permits the local emulator")
        publisher = pubsub_v1.PublisherClient()
        subscriber = pubsub_v1.SubscriberClient()
        try:
            topic_path = publisher.topic_path(project, EVENT_TOPIC_ID)
            for name, resource in names.items():
                try:
                    if name == "topic":
                        publisher.get_topic(request={"topic": topic_path}, retry=None, timeout=2)
                        results[name] = {"status": "available", "name": topic_path}
                    else:
                        path = subscriber.subscription_path(project, resource)
                        subscription = subscriber.get_subscription(
                            request={"subscription": path}, retry=None, timeout=2,
                        )
                        results[name] = {
                            "status": "available", "name": path, "topic": subscription.topic,
                            "push_endpoint": subscription.push_config.push_endpoint,
                        }
                except NotFound:
                    results[name] = {"status": "not_found"}
                except GoogleAPICallError:
                    logger.exception("Could not inspect local emulator resource %s", name)
        finally:
            publisher.transport.close()
            subscriber.transport.close()
    except (RuntimeError, GoogleAPICallError):
        logger.exception("Local emulator configuration or connection failed")
    return results


def _unknown_inventory(kind: str, resources: list[dict[str, str]] | None = None) -> dict:
    return {
        "status": "unknown",
        "resources": resources or [],
        "error": f"{kind} discovery unavailable",
    }


def _discover_topics(project_path: str) -> dict:
    resources = []
    publisher = None
    try:
        publisher = pubsub_v1.PublisherClient()
        for topic in publisher.list_topics(
            request={"project": project_path}, retry=None, timeout=2,
        ):
            resources.append({"name": topic.name})
    except GoogleAPICallError:
        logger.exception("Could not discover local Pub/Sub topics")
        return _unknown_inventory("Topic", resources)
    finally:
        if publisher is not None:
            publisher.transport.close()
    return {"status": "available", "resources": resources}


def _discover_subscriptions(project_path: str) -> dict:
    resources = []
    subscriber = None
    try:
        subscriber = pubsub_v1.SubscriberClient()
        for subscription in subscriber.list_subscriptions(
            request={"project": project_path}, retry=None, timeout=2,
        ):
            resource = {
                "name": subscription.name,
                "topic": subscription.topic,
            }
            if getattr(subscription, "ack_deadline_seconds", None) is not None:
                resource["ack_deadline_seconds"] = subscription.ack_deadline_seconds
            push_endpoint = getattr(
                getattr(subscription, "push_config", None), "push_endpoint", ""
            )
            if push_endpoint:
                resource["push_endpoint"] = _safe_push_endpoint(push_endpoint)
            retry_policy = getattr(subscription, "retry_policy", None)
            if retry_policy:
                resource["retry_policy"] = {
                    key: value
                    for key, duration in (
                        ("minimum_backoff_seconds", getattr(retry_policy, "minimum_backoff", None)),
                        ("maximum_backoff_seconds", getattr(retry_policy, "maximum_backoff", None)),
                    )
                    if duration is not None
                    for value in (getattr(duration, "seconds", None),)
                    if value is not None
                }
            dead_letter_policy = getattr(subscription, "dead_letter_policy", None)
            if dead_letter_policy and getattr(dead_letter_policy, "dead_letter_topic", ""):
                resource["dead_letter_policy"] = {
                    "topic": dead_letter_policy.dead_letter_topic,
                    "max_delivery_attempts": dead_letter_policy.max_delivery_attempts,
                }
            resources.append(resource)
    except GoogleAPICallError:
        logger.exception("Could not discover local Pub/Sub subscriptions")
        return _unknown_inventory("Subscription", resources)
    finally:
        if subscriber is not None:
            subscriber.transport.close()
    return {"status": "available", "resources": resources}


@app.get("/api/v1/pubsub/resources")
def pubsub_resources() -> dict:
    try:
        host, project = require_local_pubsub()
        if host != LOCAL_EMULATOR_HOST or project != LOCAL_PROJECT_ID:
            raise RuntimeError("Workbench only permits the local emulator")
    except RuntimeError:
        logger.exception("Local emulator configuration is unavailable")
        return {
            "topics": _unknown_inventory("Topic"),
            "subscriptions": _unknown_inventory("Subscription"),
        }

    project_path = f"projects/{project}"
    return {
        "topics": _discover_topics(project_path),
        "subscriptions": _discover_subscriptions(project_path),
    }


@app.get("/api/v1/topology")
def topology() -> dict:
    return build_topology(pubsub_resources())


@app.get("/api/v1/synthetic/templates")
def synthetic_templates(topic: str = Query(max_length=1024)) -> dict:
    synthetic.require_enabled()
    return synthetic.list_templates(topic, _discover_topics(f"projects/{LOCAL_PROJECT_ID}"))


@app.get("/api/v1/synthetic/template")
def synthetic_template(
    topic: str = Query(max_length=1024),
    origin: str = Query(max_length=1024),
    template_id: str = Query(max_length=256),
) -> dict:
    synthetic.require_enabled()
    return synthetic.get_template(
        origin, template_id, topic, _discover_topics(f"projects/{LOCAL_PROJECT_ID}"),
    )


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON constant: {value}")


def _publish_synthetic(value: dict) -> dict:
    return synthetic.publish(
        value["origin"], value["template_id"], value["topic"], value["message"],
        _discover_topics(f"projects/{LOCAL_PROJECT_ID}"),
    )


@app.post("/api/v1/synthetic/publish")
async def publish_synthetic(request: Request) -> dict:
    synthetic.require_enabled()
    synthetic.require_browser_intent(request)
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise HTTPException(status_code=415, detail="JSON content type required")
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > synthetic.MESSAGE_LIMIT:
            raise HTTPException(status_code=413, detail="Request exceeds the size limit")
    try:
        value = json.loads(data, parse_constant=_reject_json_constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise HTTPException(status_code=400, detail="Invalid JSON request") from error
    if (
        not isinstance(value, dict)
        or set(value) != {"origin", "template_id", "topic", "message"}
        or not all(isinstance(value[key], str) and 0 < len(value[key]) <= 1024
                   for key in ("origin", "template_id", "topic"))
        or not isinstance(value["message"], dict)
    ):
        raise HTTPException(status_code=400, detail="Invalid publication request")
    return await run_in_threadpool(_publish_synthetic, value)


@app.get("/api/v1/status")
def status() -> dict:
    services = {
        name: {"status": http_liveness(host), "kind": "http_liveness"}
        for name, host in {
            "publisher": "publisher",
            "item": "item-projection-consumer",
            "audit": "audit-consumer",
        }.items()
    }
    try:
        with connect(settings()) as connection:
            connection.execute("SELECT 1")
        database = "available"
    except (psycopg.Error, RuntimeError):
        logger.exception("Workbench database connection failed")
        database = "unknown"
    return {
        "checked_at": datetime.now(timezone.utc), "services": services,
        "database": {"status": database, "kind": "connection"},
        "emulator_resources": emulator_status(),
    }


@app.get("/api/v1/observations")
def list_observations(
    consumer: Literal["all", "item", "audit"] = "all",
    limit: int = Query(default=30, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=1024),
) -> dict:
    consumers = ["item", "audit"] if consumer == "all" else [consumer]
    try:
        position = decode_cursor(cursor, consumers) if cursor else None
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    result = observations(settings(), consumers, limit, position)
    if all(value == "unknown" for value in result["sources"].values()):
        raise HTTPException(status_code=503, detail="Observation sources unavailable")
    return result


@app.get("/api/v1/events/{event_id}")
def inspect_event(event_id: UUID) -> dict:
    result = event_detail(settings(), event_id)
    if all(source["status"] == "unknown" for source in result["sources"].values()):
        raise HTTPException(status_code=503, detail="Observation sources unavailable")
    return result
