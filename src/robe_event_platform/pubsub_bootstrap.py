from __future__ import annotations

import logging
import os
import sys
import time

from google.api_core.exceptions import AlreadyExists, ServiceUnavailable
from google.cloud import pubsub_v1

from robe_event_platform.local_config import (
    AUDIT_SUBSCRIPTION_ID,
    EVENT_TOPIC_ID,
    LOCAL_EMULATOR_HOST,
    LOCAL_PROJECT_ID,
    PROJECTION_SUBSCRIPTION_ID,
    require_local_pubsub,
)

logger = logging.getLogger(__name__)


def _ensure_topic(publisher: pubsub_v1.PublisherClient, topic_path: str) -> None:
    try:
        publisher.create_topic(request={"name": topic_path})
    except AlreadyExists:
        publisher.get_topic(request={"topic": topic_path})


def _ensure_push_subscription(
    subscriber: pubsub_v1.SubscriberClient,
    subscription_path: str,
    topic_path: str,
    push_endpoint: str,
) -> None:
    try:
        subscriber.create_subscription(
            request={
                "name": subscription_path,
                "topic": topic_path,
                "push_config": {"push_endpoint": push_endpoint},
            }
        )
        return
    except AlreadyExists:
        existing = subscriber.get_subscription(
            request={"subscription": subscription_path}
        )

    if existing.topic != topic_path:
        raise RuntimeError(
            f"Subscription {subscription_path} points to {existing.topic}, "
            f"not {topic_path}"
        )
    if existing.push_config.push_endpoint != push_endpoint:
        raise RuntimeError(
            f"Subscription {subscription_path} points to "
            f"{existing.push_config.push_endpoint}, not {push_endpoint}"
        )


def provision() -> None:
    emulator_host, project_id = require_local_pubsub()
    if emulator_host != LOCAL_EMULATOR_HOST or project_id != LOCAL_PROJECT_ID:
        raise RuntimeError("Only the configured local Pub/Sub emulator is allowed")

    push_endpoint = os.environ.get("PUBSUB_PUSH_ENDPOINT")
    if push_endpoint != "http://ack-fault-proxy:9000/pubsub/push":
        raise RuntimeError("PUBSUB_PUSH_ENDPOINT must target the local test proxy")
    audit_endpoint = os.environ.get("PUBSUB_AUDIT_PUSH_ENDPOINT")
    if audit_endpoint != "http://audit-ack-fault-proxy:9000/pubsub/push":
        raise RuntimeError("PUBSUB_AUDIT_PUSH_ENDPOINT must target the local audit proxy")

    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()
    topic_path = publisher.topic_path(project_id, EVENT_TOPIC_ID)
    subscription_path = subscriber.subscription_path(
        project_id, PROJECTION_SUBSCRIPTION_ID
    )
    audit_subscription_path = subscriber.subscription_path(
        project_id, AUDIT_SUBSCRIPTION_ID
    )

    last_error: ServiceUnavailable | None = None
    for attempt in range(20):
        try:
            _ensure_topic(publisher, topic_path)
            _ensure_push_subscription(
                subscriber, subscription_path, topic_path, push_endpoint
            )
            _ensure_push_subscription(
                subscriber, audit_subscription_path, topic_path, audit_endpoint
            )
            logger.info(
                "Provisioned local topic %s and push subscriptions %s and %s",
                topic_path,
                subscription_path,
                audit_subscription_path,
            )
            return
        except ServiceUnavailable as error:
            last_error = error
            time.sleep(min(0.25 * (attempt + 1), 2))
    raise RuntimeError("Local Pub/Sub emulator did not become ready") from last_error


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    provision()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Local Pub/Sub bootstrap failed")
        sys.exit(1)
