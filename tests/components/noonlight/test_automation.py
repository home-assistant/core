"""End-to-end: a sensor-triggered automation (routine) can dispatch Noonlight.

This proves the path a real user relies on — a sensor changes state, an
automation fires, and our service dispatches — works without special wiring.
"""

from __future__ import annotations

from httpx import Response
import respx

from homeassistant.components.noonlight.const import DOMAIN, STATE_DISPATCHED
from homeassistant.setup import async_setup_component

from .conftest import SANDBOX

_ALARMS = f"{SANDBOX}/dispatch/v1/alarms"


def _coordinator(hass, entry):
    return entry.runtime_data


@respx.mock
async def test_sensor_automation_dispatches(hass, setup_entry):
    """A binary_sensor turning 'on' drives an automation that dispatches."""
    create = respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "auto-1", "status": "ACTIVE"})
    )

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "alias": "Panic button dispatches police",
                "trigger": {
                    "platform": "state",
                    "entity_id": "binary_sensor.panic_button",
                    "to": "on",
                },
                "action": {
                    "service": f"{DOMAIN}.dispatch_police",
                    "data": {
                        "entry_delay_seconds": 0,
                        # Routines can template the triggering sensor in.
                        "instructions": ("Triggered by {{ trigger.to_state.name }}"),
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()

    # Sensor trips -> automation fires -> dispatch.
    hass.states.async_set("binary_sensor.panic_button", "off")
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.panic_button", "on")
    await hass.async_block_till_done()

    assert create.called
    assert _coordinator(hass, setup_entry).data["state"] == STATE_DISPATCHED


@respx.mock
async def test_script_can_cancel(hass, setup_entry):
    """A script (another routine type) can call the cancel service."""
    respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "auto-2", "status": "ACTIVE"})
    )
    coordinator = _coordinator(hass, setup_entry)
    # Put a pending dispatch in flight.
    await coordinator.async_dispatch(["police"], 60)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "abort_dispatch": {
                    "sequence": [
                        {
                            "service": f"{DOMAIN}.cancel",
                            "data": {"reason": "disarmed by script"},
                        }
                    ]
                }
            }
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call("script", "abort_dispatch", blocking=True)
    await hass.async_block_till_done()

    assert coordinator.data["state"] == "canceled"
