from __future__ import annotations

import asyncio
import base64
import binascii
import json
import os
from collections import Counter
from uuid import UUID

import httpx
from fastapi import FastAPI, Request
from pydantic import BaseModel
from starlette.responses import Response

CONSUMER_URL = os.environ.get(
    "ITEM_PROJECTION_CONSUMER_URL", "http://item-projection-consumer:8000"
)

app = FastAPI(title="Test-only Pub/Sub push fault proxy")
lock = asyncio.Lock()
held = False
ack_loss_targets: set[str] = set()
delivery_counts: Counter[str] = Counter()
ack_loss_counts: Counter[str] = Counter()
non_success_counts: Counter[str] = Counter()


class EventTarget(BaseModel):
    event_id: UUID


def event_id_from_push(body: bytes) -> str | None:
    try:
        wrapper = json.loads(body)
        encoded = wrapper["message"]["data"]
        event = json.loads(base64.b64decode(encoded, validate=True))
        return str(UUID(event["event_id"]))
    except (
        binascii.Error,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
    ):
        return None


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/__test/hold")
async def hold_pushes() -> dict[str, str]:
    global held
    async with lock:
        held = True
    return {"status": "held"}


@app.post("/__test/release")
async def release_pushes() -> dict[str, str]:
    global held
    async with lock:
        held = False
    return {"status": "released"}


@app.post("/__test/lose-ack")
async def lose_one_ack(target: EventTarget) -> dict[str, str]:
    async with lock:
        ack_loss_targets.add(str(target.event_id))
    return {"status": "armed", "event_id": str(target.event_id)}


@app.get("/__test/status/{event_id}")
async def status(event_id: UUID) -> dict[str, int]:
    key = str(event_id)
    async with lock:
        return {
            "deliveries": delivery_counts[key],
            "lost_acks": ack_loss_counts[key],
            "non_successes": non_success_counts[key],
        }


@app.post("/pubsub/push")
async def receive_push(request: Request) -> Response:
    global held
    body = await request.body()
    event_id = event_id_from_push(body)
    async with lock:
        if event_id is not None:
            delivery_counts[event_id] += 1
        is_held = held
    if is_held:
        return Response(status_code=503)

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            downstream = await client.post(
                f"{CONSUMER_URL}/pubsub/push",
                content=body,
                headers={"content-type": "application/json"},
            )
    except httpx.RequestError:
        return Response(status_code=503)

    async with lock:
        should_lose_ack = (
            event_id is not None
            and event_id in ack_loss_targets
            and downstream.status_code in {102, 200, 201, 202, 204}
        )
        if should_lose_ack:
            ack_loss_targets.remove(event_id)
            ack_loss_counts[event_id] += 1
    if should_lose_ack:
        return Response(status_code=500)

    if event_id is not None and downstream.status_code not in {102, 200, 201, 202, 204}:
        async with lock:
            non_success_counts[event_id] += 1

    return Response(
        content=downstream.content,
        status_code=downstream.status_code,
        headers={
            "content-type": downstream.headers.get(
                "content-type", "application/octet-stream"
            )
        },
    )
