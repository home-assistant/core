"""deCONZ fan platform tests."""
from copy import deepcopy

import pytest

from homeassistant.components import deconz
from homeassistant.components.deconz.gateway import get_gateway_from_config_entry
import homeassistant.components.fan as fan
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

from tests.async_mock import patch

FANS = {
    "1": {
        "etag": "432f3de28965052961a99e3c5494daf4",
        "hascolor": False,
        "manufacturername": "King Of Fans,  Inc.",
        "modelid": "HDC52EastwindFan",
        "name": "Ceiling fan",
        "state": {
            "alert": "none",
            "bri": 254,
            "on": False,
            "reachable": True,
            "speed": 4,
        },
        "swversion": "0000000F",
        "type": "Fan",
        "uniqueid": "00:22:a3:00:00:27:8b:81-01",
    }
}


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a gateway."""
    assert (
        await async_setup_component(
            hass, fan.DOMAIN, {"fan": {"platform": deconz.DOMAIN}}
        )
        is True
    )
    assert deconz.DOMAIN not in hass.data


async def test_no_fans(hass):
    """Test that no fan entities are created."""
    await setup_deconz_integration(hass)
    assert len(hass.states.async_all()) == 0


async def test_fans(hass):
    """Test that all supported fan entities are created."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["lights"] = deepcopy(FANS)
    config_entry = await setup_deconz_integration(hass, get_state_response=data)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    assert len(hass.states.async_all()) == 2  # Light and fan
    assert hass.states.get("fan.ceiling_fan")

    # Test states

    assert hass.states.get("fan.ceiling_fan").state == STATE_ON
    assert hass.states.get("fan.ceiling_fan").attributes["speed"] == fan.SPEED_HIGH

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "lights",
        "id": "1",
        "state": {"speed": 0},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    assert hass.states.get("fan.ceiling_fan").state == STATE_OFF
    assert hass.states.get("fan.ceiling_fan").attributes["speed"] == fan.SPEED_OFF

    # Test service calls

    ceiling_fan_device = gateway.api.lights["1"]

    # Service turn on fan

    with patch.object(
        ceiling_fan_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            fan.DOMAIN,
            fan.SERVICE_TURN_ON,
            {"entity_id": "fan.ceiling_fan"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/1/state", json={"speed": 4})

    # Service turn off fan

    with patch.object(
        ceiling_fan_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            fan.DOMAIN,
            fan.SERVICE_TURN_OFF,
            {"entity_id": "fan.ceiling_fan"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/1/state", json={"speed": 0})

    # Service set fan speed to low

    with patch.object(
        ceiling_fan_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            fan.DOMAIN,
            fan.SERVICE_SET_SPEED,
            {"entity_id": "fan.ceiling_fan", fan.ATTR_SPEED: fan.SPEED_LOW},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/1/state", json={"speed": 1})

    # Service set fan speed to medium

    with patch.object(
        ceiling_fan_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            fan.DOMAIN,
            fan.SERVICE_SET_SPEED,
            {"entity_id": "fan.ceiling_fan", fan.ATTR_SPEED: fan.SPEED_MEDIUM},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/1/state", json={"speed": 2})

    # Service set fan speed to high

    with patch.object(
        ceiling_fan_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            fan.DOMAIN,
            fan.SERVICE_SET_SPEED,
            {"entity_id": "fan.ceiling_fan", fan.ATTR_SPEED: fan.SPEED_HIGH},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/1/state", json={"speed": 4})

    # Service set fan speed to off

    with patch.object(
        ceiling_fan_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            fan.DOMAIN,
            fan.SERVICE_SET_SPEED,
            {"entity_id": "fan.ceiling_fan", fan.ATTR_SPEED: fan.SPEED_OFF},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/1/state", json={"speed": 0})

    # Service set fan speed to unsupported value

    with patch.object(
        ceiling_fan_device, "_request", return_value=True
    ) as set_callback, pytest.raises(ValueError):
        await hass.services.async_call(
            fan.DOMAIN,
            fan.SERVICE_SET_SPEED,
            {"entity_id": "fan.ceiling_fan", fan.ATTR_SPEED: "bad value"},
            blocking=True,
        )
        await hass.async_block_till_done()

    # Events with an unsupported speed gets converted to default speed "medium"

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "lights",
        "id": "1",
        "state": {"speed": 3},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    assert hass.states.get("fan.ceiling_fan").state == STATE_ON
    assert hass.states.get("fan.ceiling_fan").attributes["speed"] == fan.SPEED_MEDIUM

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert len(hass.states.async_all()) == 0
