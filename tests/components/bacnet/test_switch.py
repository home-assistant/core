"""Tests for the BACnet switch platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.bacnet.bacnet_client import BACnetWriteError
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import init_integration


async def test_switch_created(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that binary output objects create switch entities."""
    await init_integration(hass)

    # Fan Command (binary-output,0) - value 1 = on
    state = hass.states.get("switch.test_hvac_controller_fan_command")
    assert state is not None
    assert state.state == STATE_ON


async def test_switch_count(hass: HomeAssistant, mock_bacnet_client: AsyncMock) -> None:
    """Test the correct number of switch entities are created."""
    await init_integration(hass)

    switch_states = hass.states.async_entity_ids("switch")
    # We expect 1 switch: binary-output,0 (Fan Command)
    assert len(switch_states) == 1


async def test_turn_on(hass: HomeAssistant, mock_bacnet_client: AsyncMock) -> None:
    """Test turning on a switch entity."""
    await init_integration(hass)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_hvac_controller_fan_command"},
        blocking=True,
    )

    mock_bacnet_client.write_present_value.assert_called_once_with(
        "192.168.1.100:47808",
        "binary-output",
        0,
        "active",
    )


async def test_turn_off(hass: HomeAssistant, mock_bacnet_client: AsyncMock) -> None:
    """Test turning off a switch entity."""
    await init_integration(hass)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_hvac_controller_fan_command"},
        blocking=True,
    )

    mock_bacnet_client.write_present_value.assert_called_once_with(
        "192.168.1.100:47808",
        "binary-output",
        0,
        "inactive",
    )


async def test_turn_on_write_error(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test error handling when write fails."""
    await init_integration(hass)

    mock_bacnet_client.write_present_value.side_effect = BACnetWriteError(
        "write failed"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test_hvac_controller_fan_command"},
            blocking=True,
        )
