"""Tests for the Atomberg LED light."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
)
from homeassistant.core import HomeAssistant

from . import setup_integration

LIGHT = "light.living_room_led"
DEVICE_ID = "a4cf12abcdef"


async def test_state(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test device brightness 60 on a 10-100 scale maps into HA's 1-255 range."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(LIGHT)
    assert state.attributes[ATTR_EFFECT] == "warm"
    assert state.attributes[ATTR_BRIGHTNESS] == 143


async def test_turn_off(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test turning the LED off."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: LIGHT}, blocking=True
    )

    mock_client.async_send_command.assert_awaited_once_with(DEVICE_ID, {"led": False})
    assert hass.states.get(LIGHT).state == STATE_OFF


@pytest.mark.parametrize(
    ("service_data", "command"),
    [
        ({}, {"led": True}),
        ({ATTR_BRIGHTNESS: 255}, {"brightness": 100}),
        ({ATTR_EFFECT: "cool"}, {"light_mode": "cool"}),
        (
            {ATTR_BRIGHTNESS: 255, ATTR_EFFECT: "daylight"},
            {"brightness": 100, "light_mode": "daylight"},
        ),
    ],
)
async def test_turn_on(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service_data: dict,
    command: dict,
) -> None:
    """Test turn-on variants map to the right API command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: LIGHT, **service_data},
        blocking=True,
    )

    mock_client.async_send_command.assert_awaited_once_with(DEVICE_ID, command)
