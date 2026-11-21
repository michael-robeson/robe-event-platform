from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from google.api_core.exceptions import GoogleAPICallError
from google.cloud import pubsub_v1
from pydantic import BaseModel

from robe_event_platform.events import ItemRegisteredEvent, canonical_event_bytes
from robe_event_platform.local_config import (
    EVENT_TOPIC_ID,
    require_local_pubsub,
)

logger = logging.getLogger(__name__)


class PublishAcknowledgment(BaseModel):
    event_id: str
    pubsub_message_id: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    _, project_id = require_local_pubsub()
    app.state.publisher = pubsub_v1.PublisherClient()
    app.state.topic_path = app.state.publisher.topic_path(project_id, EVENT_TOPIC_ID)
    try:
        yield
    finally:
        app.state.publisher.transport.close()


app = FastAPI(title="Vertical Slice Demo Publisher", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/events", status_code=202, response_model=PublishAcknowledgment)
def publish_event(
    event: ItemRegisteredEvent, request: Request
) -> PublishAcknowledgment:
    try:
        future = request.app.state.publisher.publish(
            request.app.state.topic_path,
            data=canonical_event_bytes(event),
        )
        message_id = future.result()
    except (GoogleAPICallError, TimeoutError):
        logger.exception("Pub/Sub did not confirm event publication")
        raise HTTPException(
            status_code=503, detail="Pub/Sub publication was not confirmed"
        ) from None

    return PublishAcknowledgment(
        event_id=str(event.event_id),
        pubsub_message_id=message_id,
    )
