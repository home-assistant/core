"""Persistence tests for the Noonlight integration.

Dedupe timestamps and the last event survive restart, but an active dispatch
never silently resumes.
"""

from __future__ import annotations

from httpx import Response
import respx

from homeassistant.components.noonlight.const import (
    EVENT_DISPATCH_FIRED,
    STATE_DISPATCHED,
    STATE_IDLE,
    STORAGE_KEY_TEMPLATE,
)

from .conftest import SANDBOX

_ALARMS = f"{SANDBOX}/dispatch/v1/alarms"


def _coordinator(hass, entry):
    return entry.runtime_data


@respx.mock
async def test_restore_dedupe_and_last_event(hass, config_entry, hass_storage):
    """Restore a stored dedupe timestamp and last event but settle to idle.

    The stored dedupe timestamp and last event are restored on setup, but the
    machine settles to idle rather than resuming a 'dispatched' state.
    """
    respx.get(url__regex=r".*/dispatch/v1/alarms/.*/status").mock(
        return_value=Response(404)
    )
    key = STORAGE_KEY_TEMPLATE.format(entry_id=config_entry.entry_id)
    hass_storage[key] = {
        "version": 1,
        "data": {
            "last_dispatch_ts": {"police": 10_000_000_000.0},
            "last_event": {
                "type": EVENT_DISPATCH_FIRED,
                "timestamp": "2026-01-01T00:00:00+00:00",
                "state": STATE_DISPATCHED,
            },
        },
    }

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = _coordinator(hass, config_entry)
    # Dedupe timestamps were restored...
    assert coordinator._last_dispatch_ts == {"police": 10_000_000_000.0}
    # ...last event surfaced for history...
    assert coordinator.data["last_event"]["type"] == EVENT_DISPATCH_FIRED
    # ...but we did NOT resume an active alarm.
    assert coordinator.data["state"] == STATE_IDLE
    assert coordinator.data["alarm_id"] is None


@respx.mock
async def test_dispatch_persists_last_dispatch_ts(hass, setup_entry, hass_storage):
    """A dispatch persists the dedupe timestamp and last event to storage."""
    respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "abc123", "status": "ACTIVE"})
    )
    coordinator = _coordinator(hass, setup_entry)
    await coordinator.async_dispatch(["police"], 0)
    await hass.async_block_till_done()

    key = STORAGE_KEY_TEMPLATE.format(entry_id=setup_entry.entry_id)
    saved = hass_storage[key]["data"]
    assert "police" in saved["last_dispatch_ts"]
    assert saved["last_event"]["type"] == EVENT_DISPATCH_FIRED
