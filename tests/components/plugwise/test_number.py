"""Tests for the Plugwise Number integration."""

from unittest.mock import MagicMock

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

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

    assert mock_smile_anna.set_number_setpoint.call_count == 1
    mock_smile_anna.set_number_setpoint.assert_called_with(
        "maximum_boiler_temperature", "1cbf783bb11e4a7c8a6843dee3a86927", 65.0
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

    assert mock_smile_adam_2.set_number_setpoint.call_count == 1
    mock_smile_adam_2.set_number_setpoint.assert_called_with(
        "max_dhw_temperature", "056ee145a816487eaa69243c3280f8bf", 55.0
    )


async def test_adam_temperature_offset_change(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test changing of number entities."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.zone_thermostat_jessie_temperature_offset",
            ATTR_VALUE: 1.0,
        },
        blocking=True,
    )

    assert mock_smile_adam.set_temperature_offset.call_count == 1
    mock_smile_adam.set_temperature_offset.assert_called_with(
        "temperature_offset", "6a3bf693d05e48e0b460c815a4fdd09d", 1.0
    )
