"""Test the Cosa climate platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import async_update_entity

ENTITY_ID = "climate.living_room_thermostat"


@pytest.mark.usefixtures("init_integration")
async def test_climate_entity_attributes(
    hass: HomeAssistant,
    mock_cosa_api: MagicMock,
) -> None:
    """Test climate entity has correct attributes."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes["current_temperature"] == 21.5
    assert state.attributes["temperature"] == 23
    assert state.attributes["min_temp"] == 5
    assert state.attributes["max_temp"] == 35


@pytest.mark.usefixtures("init_integration")
async def test_climate_hvac_mode_off(
    hass: HomeAssistant,
    mock_cosa_api: MagicMock,
) -> None:
    """Test climate entity shows OFF when in frozen mode."""
    mock_cosa_api.async_get_endpoint.return_value = {
        "id": "endpoint-123",
        "name": "Living Room Thermostat",
        "mode": "manual",
        "option": "frozen",
        "currentTemperature": 18.0,
        "homeTemperature": 22,
        "awayTemperature": 18,
        "sleepTemperature": 19,
        "customTemperature": 23,
    }
    await async_update_entity(hass, ENTITY_ID)
    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.OFF


@pytest.mark.usefixtures("init_integration")
async def test_climate_hvac_mode_auto(
    hass: HomeAssistant,
    mock_cosa_api: MagicMock,
) -> None:
    """Test climate entity shows AUTO when in schedule mode."""
    mock_cosa_api.async_get_endpoint.return_value = {
        "id": "endpoint-123",
        "name": "Living Room Thermostat",
        "mode": "schedule",
        "option": None,
        "currentTemperature": 20.0,
        "homeTemperature": 22,
        "awayTemperature": 18,
        "sleepTemperature": 19,
        "customTemperature": 23,
    }
    await async_update_entity(hass, ENTITY_ID)
    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.AUTO


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_off(
    hass: HomeAssistant,
    mock_cosa_api: MagicMock,
) -> None:
    """Test setting HVAC mode to OFF."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    mock_cosa_api.async_disable.assert_called_once_with("endpoint-123")


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_heat(
    hass: HomeAssistant,
    mock_cosa_api: MagicMock,
) -> None:
    """Test setting HVAC mode to HEAT."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    mock_cosa_api.async_enable_custom_mode.assert_called_once_with("endpoint-123")


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_auto(
    hass: HomeAssistant,
    mock_cosa_api: MagicMock,
) -> None:
    """Test setting HVAC mode to AUTO (schedule)."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.AUTO},
        blocking=True,
    )
    mock_cosa_api.async_enable_schedule.assert_called_once_with("endpoint-123")


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature(
    hass: HomeAssistant,
    mock_cosa_api: MagicMock,
) -> None:
    """Test setting target temperature."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    mock_cosa_api.async_set_target_temperatures.assert_called_once_with(
        "endpoint-123",
        home_temp=22,
        away_temp=18,
        sleep_temp=19,
        custom_temp=25,
    )
    # Already in custom mode, so should not call enable_custom_mode again
    mock_cosa_api.async_enable_custom_mode.assert_not_called()


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_switches_to_custom_mode(
    hass: HomeAssistant,
    mock_cosa_api: MagicMock,
) -> None:
    """Test setting temperature when in schedule mode switches to custom."""
    mock_cosa_api.async_get_endpoint.return_value = {
        "id": "endpoint-123",
        "name": "Living Room Thermostat",
        "mode": "schedule",
        "option": None,
        "currentTemperature": 20.0,
        "homeTemperature": 22,
        "awayTemperature": 18,
        "sleepTemperature": 19,
        "customTemperature": 23,
    }
    await async_update_entity(hass, ENTITY_ID)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    mock_cosa_api.async_set_target_temperatures.assert_called_once()
    mock_cosa_api.async_enable_custom_mode.assert_called_once_with("endpoint-123")


@pytest.mark.usefixtures("init_integration")
async def test_turn_on(
    hass: HomeAssistant,
    mock_cosa_api: MagicMock,
) -> None:
    """Test turning on the thermostat."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_cosa_api.async_enable_custom_mode.assert_called_once_with("endpoint-123")


@pytest.mark.usefixtures("init_integration")
async def test_turn_off(
    hass: HomeAssistant,
    mock_cosa_api: MagicMock,
) -> None:
    """Test turning off the thermostat."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_cosa_api.async_disable.assert_called_once_with("endpoint-123")


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_fails(
    hass: HomeAssistant,
    mock_cosa_api: MagicMock,
) -> None:
    """Test setting HVAC mode when API fails raises error."""
    mock_cosa_api.async_disable.return_value = False
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_fails(
    hass: HomeAssistant,
    mock_cosa_api: MagicMock,
) -> None:
    """Test setting temperature when API fails raises error."""
    mock_cosa_api.async_set_target_temperatures.return_value = False
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 25},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_hvac_action_heating(
    hass: HomeAssistant,
    mock_cosa_api: MagicMock,
) -> None:
    """Test hvac_action shows heating when current < target."""
    state = hass.states.get(ENTITY_ID)
    # current is 21.5, target is 23 → heating
    assert state.attributes["hvac_action"] == HVACAction.HEATING


@pytest.mark.usefixtures("init_integration")
async def test_hvac_action_idle(
    hass: HomeAssistant,
    mock_cosa_api: MagicMock,
) -> None:
    """Test hvac_action shows idle when current >= target."""
    mock_cosa_api.async_get_endpoint.return_value = {
        "id": "endpoint-123",
        "name": "Living Room Thermostat",
        "mode": "manual",
        "option": "custom",
        "currentTemperature": 24.0,
        "homeTemperature": 22,
        "awayTemperature": 18,
        "sleepTemperature": 19,
        "customTemperature": 23,
    }
    await async_update_entity(hass, ENTITY_ID)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes["hvac_action"] == HVACAction.IDLE
