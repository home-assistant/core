"""Coordinator polling-lifecycle tests.

While a dispatch is active the coordinator polls Noonlight for status and
auto-clears on a terminal status. A transient poll failure must not clear an
active alarm.
"""

from __future__ import annotations

from httpx import Response
import respx

from homeassistant.components.noonlight.const import (
    DOMAIN,
    STATE_DISPATCHED,
    STATE_IDLE,
)

from .conftest import SANDBOX

_ALARMS = f"{SANDBOX}/dispatch/v1/alarms"
_STATUS_RE = r".*/dispatch/v1/alarms/.*/status"


def _coordinator(hass, entry):
    return hass.data[DOMAIN][entry.entry_id]


async def _dispatch_now(hass, coordinator):
    """Drive the machine into DISPATCHED with a live alarm id."""
    respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "abc123", "status": "ACTIVE"})
    )
    await coordinator.async_dispatch(["police"], 0)
    await hass.async_block_till_done()
    assert coordinator.data["state"] == STATE_DISPATCHED


@respx.mock
async def test_poll_terminal_status_clears_to_idle(hass, setup_entry):
    coordinator = _coordinator(hass, setup_entry)
    await _dispatch_now(hass, coordinator)

    respx.get(url__regex=_STATUS_RE).mock(
        return_value=Response(200, json={"status": "RESOLVED"})
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.data["state"] == STATE_IDLE
    assert coordinator.data["alarm_id"] is None


@respx.mock
async def test_poll_active_status_stays_dispatched(hass, setup_entry):
    coordinator = _coordinator(hass, setup_entry)
    await _dispatch_now(hass, coordinator)

    respx.get(url__regex=_STATUS_RE).mock(
        return_value=Response(200, json={"status": "ACTIVE"})
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.data["state"] == STATE_DISPATCHED
    assert coordinator.data["alarm_id"] == "abc123"


@respx.mock
async def test_poll_failure_keeps_active_alarm(hass, setup_entry):
    """A transient poll error must not silently clear an active alarm."""
    coordinator = _coordinator(hass, setup_entry)
    await _dispatch_now(hass, coordinator)

    respx.get(url__regex=_STATUS_RE).mock(return_value=Response(500))
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.data["state"] == STATE_DISPATCHED
    assert coordinator.data["alarm_id"] == "abc123"


@respx.mock
async def test_idle_poll_makes_no_request(hass, setup_entry):
    """While idle the coordinator must not call Noonlight at all."""
    coordinator = _coordinator(hass, setup_entry)
    status = respx.get(url__regex=_STATUS_RE).mock(return_value=Response(200))

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert not status.called
    assert coordinator.data["state"] == STATE_IDLE
