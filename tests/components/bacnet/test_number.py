"""Tests for the BACnet number platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.bacnet.bacnet_client import BACnetWriteError
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import init_integration


async def test_number_created(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that analog output objects create number entities."""
    await init_integration(hass)

    # Heating Valve (analog-output,0) - 75.0%
    state = hass.states.get("number.test_hvac_controller_heating_valve")
    assert state is not None
    assert float(state.state) == 75.0
    assert state.attributes.get("unit_of_measurement") == PERCENTAGE


async def test_number_count(hass: HomeAssistant, mock_bacnet_client: AsyncMock) -> None:
    """Test the correct number of number entities are created."""
    await init_integration(hass)

    number_states = hass.states.async_entity_ids("number")
    # We expect 1 number: analog-output,0 (Heating Valve)
    assert len(number_states) == 1


async def test_set_native_value(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test setting a value on a number entity."""
    await init_integration(hass)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_hvac_controller_heating_valve", ATTR_VALUE: 50.0},
        blocking=True,
    )

    mock_bacnet_client.write_present_value.assert_called_once_with(
        "192.168.1.100:47808",
        "analog-output",
        0,
        50.0,
    )


async def test_set_native_value_write_error(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test error handling when write fails."""
    await init_integration(hass)

    mock_bacnet_client.write_present_value.side_effect = BACnetWriteError(
        "write failed"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.test_hvac_controller_heating_valve",
                ATTR_VALUE: 50.0,
            },
            blocking=True,
        )
