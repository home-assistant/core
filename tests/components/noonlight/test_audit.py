"""Audit-log tests for the Noonlight integration.

Every dispatch appends a JSONL record, and the file is rotated once it grows
past the cap.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from httpx import Response
import respx

from homeassistant.components.noonlight import coordinator as coord_mod
from homeassistant.components.noonlight.const import EVENT_DISPATCH_FIRED

from .conftest import SANDBOX

_ALARMS = f"{SANDBOX}/dispatch/v1/alarms"


def _coordinator(hass, entry):
    return entry.runtime_data


@respx.mock
async def test_dispatch_writes_audit_lines(hass, setup_entry):
    """A dispatch appends a fired event tagged with the environment."""
    respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "abc123", "status": "ACTIVE"})
    )
    coordinator = _coordinator(hass, setup_entry)
    await coordinator.async_dispatch(["police"], 0)
    await hass.async_block_till_done()

    content = await hass.async_add_executor_job(
        Path(coordinator._audit_path).read_text
    )
    events = [json.loads(line) for line in content.splitlines() if line.strip()]

    types = [e["event"] for e in events]
    assert EVENT_DISPATCH_FIRED in types
    # Each record carries the environment it ran against.
    assert all(e["environment"] == "sandbox" for e in events)


@respx.mock
async def test_audit_log_rotates_when_oversized(hass, setup_entry, monkeypatch):
    """An oversized audit log is rotated to a .1 file on the next write."""
    monkeypatch.setattr(coord_mod, "AUDIT_MAX_BYTES", 50)
    respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "abc123", "status": "ACTIVE"})
    )
    coordinator = _coordinator(hass, setup_entry)

    os.makedirs(os.path.dirname(coordinator._audit_path), exist_ok=True)
    # Pre-fill beyond the (patched) cap so the next write triggers rotation.
    await hass.async_add_executor_job(
        Path(coordinator._audit_path).write_text, "x" * 100 + "\n"
    )

    await coordinator.async_dispatch(["police"], 0)
    await hass.async_block_till_done()

    assert os.path.exists(f"{coordinator._audit_path}.1")
    assert os.path.exists(coordinator._audit_path)
