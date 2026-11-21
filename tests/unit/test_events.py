from __future__ import annotations

from pydantic import ValidationError
import pytest

from robe_event_platform.events import (
    ItemRegisteredEvent,
    canonical_event_bytes,
    canonical_event_hash,
)


EVENT_WITH_REORDERED_KEYS = """
{
  "payload": {"label": "Example", "item_id": "item-001"},
  "source": "slice-test",
  "occurred_at": "2026-11-20T12:00:00+00:00",
  "contract_version": "1",
  "event_type": "demo.item.registered",
  "event_id": "6f3a5c1e-09c2-42d1-92d4-8e733fc9d834"
}
"""

EVENT_WITH_CANONICAL_KEYS = """
{
  "event_id": "6f3a5c1e-09c2-42d1-92d4-8e733fc9d834",
  "event_type": "demo.item.registered",
  "contract_version": "1",
  "occurred_at": "2026-11-20T12:00:00Z",
  "source": "slice-test",
  "payload": {"item_id": "item-001", "label": "Example"}
}
"""


def test_canonical_hash_normalizes_json_order_and_utc_timestamp() -> None:
    first = ItemRegisteredEvent.model_validate_json(EVENT_WITH_REORDERED_KEYS)
    second = ItemRegisteredEvent.model_validate_json(EVENT_WITH_CANONICAL_KEYS)

    assert canonical_event_bytes(first) == canonical_event_bytes(second)
    assert canonical_event_hash(first) == canonical_event_hash(second)
    assert len(canonical_event_hash(first)) == 32


@pytest.mark.parametrize(
    "payload",
    [
        {"item_id": "item-001"},
        {"item_id": "item-001", "label": "Example", "unexpected": True},
        {"item_id": "  ", "label": "Example"},
        {"item_id": "item-001", "label": ""},
    ],
)
def test_payload_rejects_missing_empty_or_unexpected_fields(
    payload: dict[str, object],
) -> None:
    raw_event = {
        "event_id": "6f3a5c1e-09c2-42d1-92d4-8e733fc9d834",
        "event_type": "demo.item.registered",
        "contract_version": "1",
        "occurred_at": "2026-11-20T12:00:00Z",
        "source": "slice-test",
        "payload": payload,
    }

    with pytest.raises(ValidationError):
        ItemRegisteredEvent.model_validate(raw_event)


def test_event_rejects_non_utc_timestamp_and_unknown_version() -> None:
    raw_event = {
        "event_id": "6f3a5c1e-09c2-42d1-92d4-8e733fc9d834",
        "event_type": "demo.item.registered",
        "contract_version": "2",
        "occurred_at": "2026-11-20T12:00:00-05:00",
        "source": "slice-test",
        "payload": {"item_id": "item-001", "label": "Example"},
    }

    with pytest.raises(ValidationError):
        ItemRegisteredEvent.model_validate(raw_event)
