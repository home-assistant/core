"""Coordinator state-machine tests."""

from __future__ import annotations

from datetime import timedelta

from httpx import Response
import respx

from homeassistant.components.noonlight.const import (
    STATE_CANCELED,
    STATE_DISPATCHED,
    STATE_IDLE,
    STATE_PENDING,
)
from homeassistant.util import dt as dt_util

from .conftest import SANDBOX

from tests.common import async_fire_time_changed

_ALARMS = f"{SANDBOX}/dispatch/v1/alarms"


def _coordinator(hass, entry):
    return entry.runtime_data


@respx.mock
async def test_dispatch_with_zero_delay_fires_immediately(hass, setup_entry):
    create = respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "abc123", "status": "ACTIVE"})
    )
    coordinator = _coordinator(hass, setup_entry)

    await coordinator.async_dispatch(["police"], 0)
    await hass.async_block_till_done()

    assert create.called
    assert coordinator.data["state"] == STATE_DISPATCHED
    assert coordinator.data["alarm_id"] == "abc123"
    assert hass.states.get("binary_sensor.noonlight_main_dispatch_active").state == "on"


@respx.mock
async def test_entry_delay_timer_then_fire(hass, setup_entry):
    create = respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "abc123", "status": "ACTIVE"})
    )
    coordinator = _coordinator(hass, setup_entry)

    await coordinator.async_dispatch(["police"], 5)
    await hass.async_block_till_done()
    assert coordinator.data["state"] == STATE_PENDING
    assert not create.called

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done()

    assert create.called
    assert coordinator.data["state"] == STATE_DISPATCHED


@respx.mock
async def test_cancel_during_entry_delay_makes_no_call(hass, setup_entry):
    create = respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "abc123", "status": "ACTIVE"})
    )
    coordinator = _coordinator(hass, setup_entry)

    await coordinator.async_dispatch(["police"], 30)
    await hass.async_block_till_done()
    assert coordinator.data["state"] == STATE_PENDING

    await coordinator.async_cancel("disarmed")
    await hass.async_block_till_done()
    assert coordinator.data["state"] == STATE_CANCELED
    assert not create.called

    # After the settle window the machine returns to idle.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()
    assert coordinator.data["state"] == STATE_IDLE


@respx.mock
async def test_dedupe_suppresses_repeat_dispatch(hass, setup_entry):
    create = respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "abc123", "status": "ACTIVE"})
    )
    coordinator = _coordinator(hass, setup_entry)

    await coordinator.async_dispatch(["police"], 0)
    await hass.async_block_till_done()
    assert create.call_count == 1

    # Inside the 300s dedupe window: the repeat is a no-op.
    await coordinator.async_dispatch(["police"], 0)
    await hass.async_block_till_done()
    assert create.call_count == 1


@respx.mock
async def test_dedupe_disabled_allows_repeat(hass, setup_entry):
    """With the dedupe window set to 0, repeats always fire."""
    hass.config_entries.async_update_entry(
        setup_entry, options={**setup_entry.options, "dedupe_seconds": 0}
    )
    await hass.async_block_till_done()
    create = respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "abc123", "status": "ACTIVE"})
    )
    coordinator = _coordinator(hass, setup_entry)

    await coordinator.async_dispatch(["police"], 0)
    await hass.async_block_till_done()
    await coordinator.async_dispatch(["police"], 0)
    await hass.async_block_till_done()

    assert create.call_count == 2
