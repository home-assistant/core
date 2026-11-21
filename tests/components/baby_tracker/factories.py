"""Builders for the invented sync-format payloads in ``components/baby_tracker/fixtures/``.

The JSON files hold each payload's shape. A builder fills in the fields a test varies.
Nothing here comes from a real account.
"""

import base64
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
import json
from typing import Any

from pytest_homeassistant.common import load_json_object_fixture

from homeassistant.components.baby_tracker.const import DOMAIN

BABY_ONE_ID = "11111111-AAAA-4AAA-8AAA-000000000001"
BABY_TWO_ID = "22222222-BBBB-4BBB-8BBB-000000000002"
BABY_THREE_ID = "33333333-CCCC-4CCC-8CCC-000000000003"

DEVICE_A = "AAAAAAAA-0000-4000-8000-00000000000A"
DEVICE_B = "BBBBBBBB-0000-4000-8000-00000000000B"

BASE_TIME = datetime(2026, 10, 25, 12, 0, 0, tzinfo=UTC)

OP_ADD = 0
OP_UPDATE = 1
OP_DELETE = 2


def at(minutes: float = 0) -> datetime:
    """A moment, in minutes after the fixed base time."""
    return BASE_TIME + timedelta(minutes=minutes)


def fmt(moment: datetime) -> str:
    """Format a moment the way the sync service writes times."""
    return moment.strftime("%Y-%m-%d %H:%M:%S %z")


def volume(value: float, *, english: bool = True) -> dict[str, Any]:
    """A sync-format volume, as the app writes it."""
    payload = dict(load_json_object_fixture("volume.json", DOMAIN))
    payload["englishMeasure"] = "true" if english else "false"
    payload["value"] = value
    return payload


def baby_payload(name: str, object_id: str) -> dict[str, Any]:
    """A baby's payload, with its name and ID."""
    payload = dict(load_json_object_fixture("baby.json", DOMAIN))
    payload["name"] = name
    payload["objectID"] = object_id
    return payload


def record_payload(
    type_name: str,
    object_id: str,
    *,
    when: datetime,
    baby: Mapping[str, Any] | None,
    changed: datetime | None = None,
    note: str = "",
    **fields: Any,
) -> dict[str, Any]:
    """A record payload.

    ``baby=None`` leaves the ``baby`` key out, as the live service does for a pump.
    """
    payload = dict(load_json_object_fixture("record.json", DOMAIN))
    payload["BCObjectType"] = type_name
    payload["objectID"] = object_id
    payload["time"] = fmt(when)
    payload["timestamp"] = fmt(changed or when)
    payload["note"] = note
    payload.update(fields)
    if baby is not None:
        payload["baby"] = dict(baby)
    return payload


def wire(sync_id: int, op_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    """One entry as the service returns it from a device's log."""
    text = json.dumps(payload).encode("utf-8")
    entry = dict(load_json_object_fixture("wire.json", DOMAIN))
    entry["SyncID"] = sync_id
    entry["OPCode"] = op_code
    entry["Transaction"] = base64.b64encode(text).decode()
    return entry
