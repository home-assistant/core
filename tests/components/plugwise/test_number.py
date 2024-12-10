"""Tests for the Plugwise Number integration."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry


async def test_anna_number_entities(
    hass: HomeAssistant, mock_smile_anna: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of a number."""
    state = hass.states.get("number.opentherm_maximum_boiler_temperature_setpoint")
    assert state
    assert float(state.state) == 60.0


async def test_anna_max_boiler_temp_change(
    hass: HomeAssistant, mock_smile_anna: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test changing of number entities."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.opentherm_maximum_boiler_temperature_setpoint",
            ATTR_VALUE: 65,
        },
        blocking=True,
    )

    assert mock_smile_anna.set_number.call_count == 1
    mock_smile_anna.set_number.assert_called_with(
        "1cbf783bb11e4a7c8a6843dee3a86927", "maximum_boiler_temperature", 65.0
    )


async def test_adam_number_entities(
    hass: HomeAssistant, mock_smile_adam_2: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of a number."""
    state = hass.states.get("number.opentherm_domestic_hot_water_setpoint")
    assert state
    assert float(state.state) == 60.0


async def test_adam_dhw_setpoint_change(
    hass: HomeAssistant, mock_smile_adam_2: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test changing of number entities."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.opentherm_domestic_hot_water_setpoint",
            ATTR_VALUE: 55,
        },
        blocking=True,
    )

    assert mock_smile_adam_2.set_number.call_count == 1
    mock_smile_adam_2.set_number.assert_called_with(
        "056ee145a816487eaa69243c3280f8bf", "max_dhw_temperature", 55.0
    )


async def test_adam_temperature_offset(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of the temperature_offset number."""
    state = hass.states.get("number.zone_thermostat_jessie_temperature_offset")
    assert state
    assert float(state.state) == 0.0
    assert state.attributes.get("min") == -2.0
    assert state.attributes.get("max") == 2.0
    assert state.attributes.get("step") == 0.1


async def test_adam_temperature_offset_change(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test changing of the temperature_offset number."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.zone_thermostat_jessie_temperature_offset",
            ATTR_VALUE: 1.0,
        },
        blocking=True,
    )

    assert mock_smile_adam.set_number.call_count == 1
    mock_smile_adam.set_number.assert_called_with(
        "6a3bf693d05e48e0b460c815a4fdd09d", "temperature_offset", 1.0
    )


async def test_adam_temperature_offset_out_of_bounds_change(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test changing of the temperature_offset number beyond limits."""
    with pytest.raises(ServiceValidationError, match="valid range"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.zone_thermostat_jessie_temperature_offset",
                ATTR_VALUE: 3.0,
            },
            blocking=True,
        )
