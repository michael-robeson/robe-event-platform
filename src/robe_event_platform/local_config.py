from __future__ import annotations

import os


LOCAL_PROJECT_ID = "robe-local"
LOCAL_EMULATOR_HOST = "pubsub:8085"
EVENT_TOPIC_ID = "demo-events"
PROJECTION_SUBSCRIPTION_ID = "demo-item-projection"
AUDIT_SUBSCRIPTION_ID = "demo-item-audit"


def require_local_pubsub() -> tuple[str, str]:
    emulator_host = os.environ.get("PUBSUB_EMULATOR_HOST")
    project_id = os.environ.get("PUBSUB_PROJECT_ID")
    if emulator_host != LOCAL_EMULATOR_HOST:
        raise RuntimeError(
            f"PUBSUB_EMULATOR_HOST must be {LOCAL_EMULATOR_HOST!r}; "
            "this slice cannot publish to GCP"
        )
    if project_id != LOCAL_PROJECT_ID:
        raise RuntimeError(
            f"PUBSUB_PROJECT_ID must be {LOCAL_PROJECT_ID!r}; "
            "this slice cannot publish to GCP"
        )
    return emulator_host, project_id
