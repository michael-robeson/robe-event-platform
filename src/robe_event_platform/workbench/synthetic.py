from __future__ import annotations

import json
import logging
import os
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any
from urllib.error import URLError
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from google.api_core.exceptions import GoogleAPICallError
from google.cloud import pubsub_v1
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError
from referencing import Registry
from referencing.exceptions import Unresolvable

from robe_event_platform.local_config import LOCAL_PROJECT_ID, require_local_pubsub
from robe_event_platform.workbench import topology

logger = logging.getLogger(__name__)
MESSAGE_LIMIT = 64 * 1024


def require_enabled() -> None:
    if os.environ.get("WORKBENCH_SYNTHETIC_PUBLISH_ENABLED") != "true":
        raise HTTPException(status_code=403, detail="Synthetic publication is disabled")
    try:
        require_local_pubsub()
    except RuntimeError as error:
        logger.warning("Synthetic publication blocked: %s", error)
        raise HTTPException(status_code=503, detail="Local emulator configuration unavailable") from error


def require_browser_intent(request: Request) -> None:
    if request.headers.get("x-workbench-intent") != "synthetic-publication":
        raise HTTPException(status_code=403, detail="Explicit synthetic publication intent required")
    if request.url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(status_code=403, detail="Publication requires a loopback host")
    origin = request.headers.get("origin")
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme != "http" or parsed.netloc != request.headers.get("host") or parsed.path:
            raise HTTPException(status_code=403, detail="Publication origin is not the local Workbench")


def _observed_topic(topic: str, inventory: dict[str, Any]) -> None:
    if inventory["status"] != "available":
        raise HTTPException(status_code=503, detail="Local topic discovery unavailable")
    if not topic.startswith(f"projects/{LOCAL_PROJECT_ID}/topics/") or not any(
        item["name"] == topic for item in inventory["resources"]
    ):
        raise HTTPException(status_code=404, detail="Topic is not observed in the local emulator")


def _templates(descriptor: dict[str, Any]) -> list[dict[str, str]]:
    messaging = descriptor["messaging"]
    declarations = messaging.get("synthetic_templates", [])
    if not isinstance(declarations, list):
        raise ValueError("synthetic_templates must be an array")
    declared_topics = {item["id"] for item in messaging["topics"]}
    ids: set[str] = set()
    result = []
    for item in declarations:
        if not isinstance(item, dict):
            raise ValueError("synthetic template must be an object")
        template_id = topology._nonempty(item.get("id"), "template.id")
        name = topology._nonempty(item.get("name"), "template.name")
        topic_id = topology._nonempty(item.get("topic_id"), "template.topic_id")
        if "/" in template_id or template_id in ids or topic_id not in declared_topics:
            raise ValueError("template ids must be unique and topics must be declared")
        result.append({
            "id": template_id,
            "name": name,
            "topic_id": topic_id,
            "template_path": topology._relative_path(item.get("template_path")),
            "contract_path": topology._relative_path(item.get("contract_path")),
        })
        ids.add(template_id)
    return result


def _descriptor(origin: str) -> dict[str, Any]:
    try:
        return topology._validate_descriptor(
            topology._read_json(f"{origin}{topology.DESCRIPTOR_PATH}")
        )
    except (URLError, TimeoutError, OSError, ValueError, UnicodeError) as error:
        logger.warning("Synthetic template provider %s unavailable: %s", origin, error)
        raise HTTPException(status_code=503, detail=f"Service descriptor unavailable: {origin}") from error


def _resolve(origin: str, template_id: str, topic: str) -> dict[str, str]:
    if origin not in topology._service_urls():
        raise HTTPException(status_code=404, detail="Template provider is not configured")
    descriptor = _descriptor(origin)
    if descriptor["messaging"]["project_id"] != LOCAL_PROJECT_ID:
        raise HTTPException(status_code=404, detail="Template is not declared for the local project")
    try:
        templates = _templates(descriptor)
    except ValueError as error:
        logger.warning("Invalid synthetic templates from %s: %s", origin, error)
        raise HTTPException(status_code=502, detail="Invalid service template declaration") from error
    for item in templates:
        if item["id"] == template_id and topic == f"projects/{LOCAL_PROJECT_ID}/topics/{item['topic_id']}":
            return item
    raise HTTPException(status_code=404, detail="Template is not declared for this topic")


def list_templates(topic: str, inventory: dict[str, Any]) -> dict[str, Any]:
    require_enabled()
    _observed_topic(topic, inventory)
    templates: list[dict[str, str]] = []
    errors: list[str] = []
    for origin in topology._service_urls():
        try:
            descriptor = _descriptor(origin)
            if descriptor["messaging"]["project_id"] != LOCAL_PROJECT_ID:
                continue
            for item in _templates(descriptor):
                if topic == f"projects/{LOCAL_PROJECT_ID}/topics/{item['topic_id']}":
                    templates.append({
                        "id": item["id"], "name": item["name"], "origin": origin,
                        "service": descriptor["service"]["name"],
                    })
        except (HTTPException, ValueError) as error:
            logger.warning("Cannot list synthetic templates from %s: %s", origin, error)
            errors.append(f"Templates unavailable from {origin}")
    return {"templates": templates, "errors": errors}


def _service_json(origin: str, path: str) -> dict[str, Any]:
    try:
        return topology._read_json(f"{origin}{path}")
    except (URLError, TimeoutError, OSError, ValueError, UnicodeError) as error:
        logger.warning("Synthetic template resource unavailable from %s: %s", origin, error)
        raise HTTPException(status_code=502, detail="Service template or contract unavailable") from error


def get_template(origin: str, template_id: str, topic: str, inventory: dict[str, Any]) -> dict[str, Any]:
    require_enabled()
    _observed_topic(topic, inventory)
    item = _resolve(origin, template_id, topic)
    message = _service_json(origin, item["template_path"])
    if "payload" not in message:
        raise HTTPException(status_code=502, detail="Service template has no payload")
    try:
        _validate_contract(_service_json(origin, item["contract_path"]), message)
    except HTTPException as error:
        if error.status_code == 422:
            raise HTTPException(status_code=502, detail="Service template does not match its contract") from error
        raise
    return message


def _validate_contract(schema: dict[str, Any], message: dict[str, Any]) -> None:
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise HTTPException(status_code=502, detail="Unsupported service contract schema")
    try:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema, format_checker=FormatChecker(), registry=Registry()).validate(message)
    except SchemaError as error:
        logger.warning("Invalid service contract: %s", error.message)
        raise HTTPException(status_code=502, detail="Invalid service contract") from error
    except Unresolvable as error:
        logger.warning("Service contract reference cannot be resolved locally: %s", error)
        raise HTTPException(status_code=502, detail="Service contract contains an unresolved reference") from error
    except ValidationError as error:
        path = ".".join(str(part) for part in error.absolute_path) or "message"
        raise HTTPException(status_code=422, detail=f"{path}: {error.message}") from error


def publish(
    origin: str, template_id: str, topic: str, message: dict[str, Any], inventory: dict[str, Any],
) -> dict[str, Any]:
    require_enabled()
    _observed_topic(topic, inventory)
    item = _resolve(origin, template_id, topic)
    schema = _service_json(origin, item["contract_path"])
    _validate_contract(schema, message)
    try:
        data = json.dumps(message, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError) as error:
        raise HTTPException(status_code=400, detail="Message is not valid finite JSON") from error
    if len(data) > MESSAGE_LIMIT:
        raise HTTPException(status_code=413, detail="Message exceeds the size limit")
    publisher = None
    try:
        publisher = pubsub_v1.PublisherClient()
        message_id = publisher.publish(topic, data, retry=None, timeout=5).result(timeout=6)
    except FutureTimeout as error:
        logger.warning("Synthetic publication outcome unknown for %s", topic)
        raise HTTPException(
            status_code=504,
            detail="Broker response timed out; acceptance is unknown. Do not retry blindly.",
        ) from error
    except (GoogleAPICallError, OSError) as error:
        logger.exception("Synthetic publication failed for %s", topic)
        raise HTTPException(
            status_code=502, detail="Broker acceptance could not be confirmed; do not retry blindly.",
        ) from error
    finally:
        if publisher is not None:
            publisher.transport.close()
    return {
        "status": "broker_accepted",
        "topic": topic,
        "message_id": message_id,
        "event_id": message.get("event_id"),
        "correlation_id": message.get("correlation_id"),
        "causation_id": message.get("causation_id"),
    }
