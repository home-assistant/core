"""Tests for fan platform."""

from typing import Any
from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.components.wiz.fan import PRESET_MODE_BREEZE
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import FAKE_DIMMABLE_FAN, FAKE_MAC, async_push_update, async_setup_integration

from tests.common import snapshot_platform

ENTITY_ID = "fan.mock_title"

INITIAL_PARAMS = {
    "mac": FAKE_MAC,
    "fanState": 0,
    "fanMode": 1,
    "fanSpeed": 1,
    "fanRevrs": 0,
}


@patch("homeassistant.components.wiz.PLATFORMS", [Platform.FAN])
async def test_entity(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Test the fan entity."""
    entry = (await async_setup_integration(hass, bulb_type=FAKE_DIMMABLE_FAN))[1]
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


def _update_params(
    params: dict[str, Any],
    state: int | None = None,
    mode: int | None = None,
    speed: int | None = None,
    reverse: int | None = None,
) -> dict[str, Any]:
    """Get the parameters for the update."""
    if state is not None:
        params["fanState"] = state
    if mode is not None:
        params["fanMode"] = mode
    if speed is not None:
        params["fanSpeed"] = speed
    if reverse is not None:
        params["fanRevrs"] = reverse
    return params


async def test_turn_on_off(hass: HomeAssistant) -> None:
    """Test turning the fan on and off."""
    device, _ = await async_setup_integration(hass, bulb_type=FAKE_DIMMABLE_FAN)

    params = INITIAL_PARAMS.copy()

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    calls = device.fan_turn_on.mock_calls
    assert len(calls) == 1
    args = calls[0][2]
    assert args == {"mode": None, "speed": None}
    await async_push_update(hass, device, _update_params(params, state=1, **args))
    device.fan_turn_on.reset_mock()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_MODE_BREEZE},
        blocking=True,
    )
    calls = device.fan_turn_on.mock_calls
    assert len(calls) == 1
    args = calls[0][2]
    assert args == {"mode": 2, "speed": None}
    await async_push_update(hass, device, _update_params(params, state=1, **args))
    device.fan_turn_on.reset_mock()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_MODE_BREEZE

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE: 50},
        blocking=True,
    )
    calls = device.fan_turn_on.mock_calls
    assert len(calls) == 1
    args = calls[0][2]
    assert args == {"mode": 1, "speed": 3}
    await async_push_update(hass, device, _update_params(params, state=1, **args))
    device.fan_turn_on.reset_mock()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 50
    assert state.attributes[ATTR_PRESET_MODE] is None

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    calls = device.fan_turn_off.mock_calls
    assert len(calls) == 1
    await async_push_update(hass, device, _update_params(params, state=0))
    device.fan_turn_off.reset_mock()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF


async def test_fan_set_preset_mode(hass: HomeAssistant) -> None:
    """Test setting the fan preset mode."""
    device, _ = await async_setup_integration(hass, bulb_type=FAKE_DIMMABLE_FAN)

    params = INITIAL_PARAMS.copy()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_MODE_BREEZE},
        blocking=True,
    )
    calls = device.fan_set_state.mock_calls
    assert len(calls) == 1
    args = calls[0][2]
    assert args == {"mode": 2}
    await async_push_update(hass, device, _update_params(params, state=1, **args))
    device.fan_set_state.reset_mock()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_MODE_BREEZE


async def test_fan_set_percentage(hass: HomeAssistant) -> None:
    """Test setting the fan percentage."""
    device, _ = await async_setup_integration(hass, bulb_type=FAKE_DIMMABLE_FAN)

    params = INITIAL_PARAMS.copy()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE: 50},
        blocking=True,
    )
    calls = device.fan_set_state.mock_calls
    assert len(calls) == 1
    args = calls[0][2]
    assert args == {"mode": 1, "speed": 3}
    await async_push_update(hass, device, _update_params(params, state=1, **args))
    device.fan_set_state.reset_mock()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 50

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE: 0},
        blocking=True,
    )
    calls = device.fan_turn_off.mock_calls
    assert len(calls) == 1
    await async_push_update(hass, device, _update_params(params, state=0))
    device.fan_set_state.reset_mock()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_PERCENTAGE] == 50


async def test_fan_set_direction(hass: HomeAssistant) -> None:
    """Test setting the fan direction."""
    device, _ = await async_setup_integration(hass, bulb_type=FAKE_DIMMABLE_FAN)

    params = INITIAL_PARAMS.copy()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_DIRECTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_DIRECTION: DIRECTION_REVERSE},
        blocking=True,
    )
    calls = device.fan_set_state.mock_calls
    assert len(calls) == 1
    args = calls[0][2]
    assert args == {"reverse": 1}
    await async_push_update(hass, device, _update_params(params, **args))
    device.fan_set_state.reset_mock()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_DIRECTION] == DIRECTION_REVERSE

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_DIRECTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_DIRECTION: DIRECTION_FORWARD},
        blocking=True,
    )
    calls = device.fan_set_state.mock_calls
    assert len(calls) == 1
    args = calls[0][2]
    assert args == {"reverse": 0}
    await async_push_update(hass, device, _update_params(params, **args))
    device.fan_set_state.reset_mock()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_DIRECTION] == DIRECTION_FORWARD
