"""Tests for the WiLight integration."""
from unittest.mock import patch

import pytest
import pywilight

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_SPEED,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_SPEED,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.helpers.typing import HomeAssistantType

from . import (
    HOST,
    UPNP_MAC_ADDRESS,
    UPNP_MODEL_NAME_LIGHT_FAN,
    UPNP_MODEL_NUMBER,
    UPNP_SERIAL,
    WILIGHT_ID,
    setup_integration,
)


@pytest.fixture(name="dummy_device_from_host_light_fan")
def mock_dummy_device_from_host_light_fan():
    """Mock a valid api_devce."""

    device = pywilight.wilight_from_discovery(
        f"http://{HOST}:45995/wilight.xml",
        UPNP_MAC_ADDRESS,
        UPNP_MODEL_NAME_LIGHT_FAN,
        UPNP_SERIAL,
        UPNP_MODEL_NUMBER,
    )

    device.set_dummy(True)

    with patch(
        "pywilight.device_from_host",
        return_value=device,
    ):
        yield device


async def test_loading_light_fan(
    hass: HomeAssistantType,
    dummy_device_from_host_light_fan,
) -> None:
    """Test the WiLight configuration entry loading."""

    entry = await setup_integration(hass)
    assert entry
    assert entry.unique_id == WILIGHT_ID

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    # First segment of the strip
    state = hass.states.get("fan.wl000000000099_2")
    assert state
    assert state.state == STATE_OFF

    entry = entity_registry.async_get("fan.wl000000000099_2")
    assert entry
    assert entry.unique_id == "WL000000000099_1"


async def test_on_off_fan_state(
    hass: HomeAssistantType, dummy_device_from_host_light_fan
) -> None:
    """Test the change of state of the fan switches."""
    await setup_integration(hass)

    # Turn on
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.wl000000000099_2"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("fan.wl000000000099_2")
    assert state
    assert state.state == STATE_ON

    # Turn on with speed
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_SPEED: SPEED_LOW, ATTR_ENTITY_ID: "fan.wl000000000099_2"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("fan.wl000000000099_2")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_SPEED) == SPEED_LOW

    # Turn off
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "fan.wl000000000099_2"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("fan.wl000000000099_2")
    assert state
    assert state.state == STATE_OFF


async def test_speed_fan_state(
    hass: HomeAssistantType, dummy_device_from_host_light_fan
) -> None:
    """Test the change of speed of the fan switches."""
    await setup_integration(hass)

    # Set speed Low
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_SPEED,
        {ATTR_SPEED: SPEED_LOW, ATTR_ENTITY_ID: "fan.wl000000000099_2"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("fan.wl000000000099_2")
    assert state
    assert state.attributes.get(ATTR_SPEED) == SPEED_LOW

    # Set speed Medium
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_SPEED,
        {ATTR_SPEED: SPEED_MEDIUM, ATTR_ENTITY_ID: "fan.wl000000000099_2"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("fan.wl000000000099_2")
    assert state
    assert state.attributes.get(ATTR_SPEED) == SPEED_MEDIUM

    # Set speed High
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_SPEED,
        {ATTR_SPEED: SPEED_HIGH, ATTR_ENTITY_ID: "fan.wl000000000099_2"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("fan.wl000000000099_2")
    assert state
    assert state.attributes.get(ATTR_SPEED) == SPEED_HIGH


async def test_direction_fan_state(
    hass: HomeAssistantType, dummy_device_from_host_light_fan
) -> None:
    """Test the change of direction of the fan switches."""
    await setup_integration(hass)

    # Set direction Forward
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_DIRECTION,
        {ATTR_DIRECTION: DIRECTION_FORWARD, ATTR_ENTITY_ID: "fan.wl000000000099_2"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("fan.wl000000000099_2")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_DIRECTION) == DIRECTION_FORWARD

    # Set direction Reverse
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_DIRECTION,
        {ATTR_DIRECTION: DIRECTION_REVERSE, ATTR_ENTITY_ID: "fan.wl000000000099_2"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("fan.wl000000000099_2")
    assert state
    assert state.attributes.get(ATTR_DIRECTION) == DIRECTION_REVERSE
