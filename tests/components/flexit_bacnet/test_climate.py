"""Tests for the Flexit Nordic (BACnet) climate entity."""

import asyncio
from unittest.mock import AsyncMock

from flexit_bacnet import (
    VENTILATION_MODE_AWAY,
    VENTILATION_MODE_HOME,
    VENTILATION_MODE_STOP,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    PRESET_AWAY,
    PRESET_HOME,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.components.flexit_bacnet.const import PRESET_TO_VENTILATION_MODE_MAP
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_component, entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "climate.device_name"


async def test_climate_entity(
    hass: HomeAssistant,
    mock_flexit_bacnet: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the initial parameters."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_hvac_preset_mode(
    hass: HomeAssistant,
    mock_flexit_bacnet: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the initial parameters."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Set preset mode to away
    mock_flexit_bacnet.ventilation_mode = VENTILATION_MODE_AWAY
    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_PRESET_MODE: PRESET_AWAY,
        },
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_AWAY

    mock_flexit_bacnet.set_ventilation_mode.assert_called_once_with(
        PRESET_TO_VENTILATION_MODE_MAP[PRESET_AWAY]
    )

    # Set preset mode to home
    mock_flexit_bacnet.ventilation_mode = VENTILATION_MODE_HOME
    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_PRESET_MODE: PRESET_HOME,
        },
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_HOME

    mock_flexit_bacnet.set_ventilation_mode.assert_called_with(
        PRESET_TO_VENTILATION_MODE_MAP[PRESET_HOME]
    )

    mock_flexit_bacnet.set_ventilation_mode.side_effect = asyncio.TimeoutError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.CLIMATE,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_PRESET_MODE: PRESET_AWAY,
            },
            blocking=True,
        )

    mock_flexit_bacnet.set_ventilation_mode.assert_called_with(
        PRESET_TO_VENTILATION_MODE_MAP[PRESET_AWAY]
    )


async def test_set_hvac_mode(
    hass: HomeAssistant,
    mock_flexit_bacnet: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting HVAC mode."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    mock_flexit_bacnet.ventilation_mode = VENTILATION_MODE_STOP
    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.OFF
    mock_flexit_bacnet.set_ventilation_mode.assert_called_once_with(
        VENTILATION_MODE_STOP
    )

    mock_flexit_bacnet.set_ventilation_mode.side_effect = asyncio.TimeoutError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.CLIMATE,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
            blocking=True,
        )

    mock_flexit_bacnet.set_ventilation_mode.assert_called_with(VENTILATION_MODE_STOP)


async def test_hvac_action(
    hass: HomeAssistant,
    mock_flexit_bacnet: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test hvac_action property."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Simulate electric heater being ON
    mock_flexit_bacnet.electric_heater = True
    await entity_component.async_update_entity(hass, ENTITY_ID)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING

    # Simulate electric heater being OFF
    mock_flexit_bacnet.electric_heater = False
    await entity_component.async_update_entity(hass, ENTITY_ID)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.FAN


async def test_set_temperature(
    hass: HomeAssistant,
    mock_flexit_bacnet: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting the temperature."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Set ventilation mode to HOME and set temperature to 22.5°C
    mock_flexit_bacnet.ventilation_mode = VENTILATION_MODE_HOME
    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 22.5,
        },
        blocking=True,
    )

    # Ensure that the correct method was called
    mock_flexit_bacnet.set_air_temp_setpoint_home.assert_called_once_with(22.5)

    # Change ventilation mode to AWAY and set temperature
    mock_flexit_bacnet.ventilation_mode = VENTILATION_MODE_AWAY
    await hass.services.async_call(
        Platform.CLIMATE,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 18.0,
        },
        blocking=True,
    )

    # Ensure that the correct method was called
    mock_flexit_bacnet.set_air_temp_setpoint_away.assert_called_once_with(18.0)

    # Test handling of connection errors
    mock_flexit_bacnet.set_air_temp_setpoint_away.side_effect = ConnectionError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.CLIMATE,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_TEMPERATURE: 20.0,
            },
            blocking=True,
        )
