from __future__ import annotations

import base64
import binascii
import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, Request, Response
from pydantic import BaseModel, ConfigDict, ValidationError
from starlette.concurrency import run_in_threadpool

from robe_event_platform.audit_database import apply_audit_event
from robe_event_platform.database import DatabaseSettings, EventIdentityConflict
from robe_event_platform.events import ItemRegisteredEvent

logger = logging.getLogger(__name__)


class PubSubMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    data: str


class PubSubPushRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: PubSubMessage
    subscription: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.database = DatabaseSettings.from_environment()
    yield


app = FastAPI(title="Demo Audit Projection Consumer", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/pubsub/push", status_code=204)
async def receive_push(request: Request) -> Response:
    try:
        push = PubSubPushRequest.model_validate(await request.json())
        event_bytes = base64.b64decode(push.message.data, validate=True)
        event = ItemRegisteredEvent.model_validate_json(event_bytes)
    except (
        binascii.Error,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValidationError,
        ValueError,
        TypeError,
    ):
        logger.warning("Rejected malformed Pub/Sub push request")
        return Response(status_code=400)

    try:
        await run_in_threadpool(apply_audit_event, request.app.state.database, event)
    except EventIdentityConflict:
        logger.error(
            "Audit event ID was reused with different content",
            extra={"event_id": str(event.event_id), "source": event.source},
        )
        return Response(status_code=409)
    except psycopg.Error:
        logger.exception(
            "Audit database processing failed",
            extra={"event_id": str(event.event_id), "source": event.source},
        )
        return Response(status_code=503)
    return Response(status_code=204)
