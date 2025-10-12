"""Test Control4 Climate."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTITY_ID = "climate.studio"


async def _setup_integration_with_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_director_variables: dict,
) -> None:
    """Set up the Control4 integration with custom data."""
    mock_config_entry.add_to_hass(hass)

    async def mock_update_variables(*args, **kwargs):
        """Mock update variables function."""
        return mock_director_variables

    mock_director_all_items = [
        {
            "id": 123,
            "name": "Residential Thermostat V2",
            "type": 1,
            "parentId": 456,
            "categories": ["comfort"],
        },
        {
            "id": 456,
            "manufacturer": "Control4",
            "roomName": "Studio",
            "model": "C4-TSTAT",
        },
    ]

    mock_director = MagicMock()
    mock_director.getAllItemInfo = AsyncMock(
        return_value=json.dumps(mock_director_all_items)
    )

    mock_account = MagicMock()
    mock_account.getAccountBearerToken = AsyncMock()
    mock_account.getAccountControllers = AsyncMock(
        return_value={"href": "https://example.com/controller"}
    )
    mock_account.getDirectorBearerToken = AsyncMock(
        return_value={"token": "test-token"}
    )
    mock_account.getControllerOSVersion = AsyncMock(return_value="3.2.0")

    with (
        patch(
            "homeassistant.components.control4.C4Account",
            return_value=mock_account,
        ),
        patch(
            "homeassistant.components.control4.C4Director",
            return_value=mock_director,
        ),
        patch(
            "homeassistant.components.control4.director_utils.update_variables_for_config_entry",
            new=mock_update_variables,
        ),
        patch(
            "homeassistant.components.control4.PLATFORMS",
            ["climate"],
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.usefixtures("init_integration")
async def test_climate_setup(hass: HomeAssistant) -> None:
    """Test climate entity is set up correctly."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes["current_temperature"] == 72.5
    assert state.attributes["current_humidity"] == 45
    assert state.attributes["temperature"] == 68.0
    assert state.attributes["hvac_action"] == HVACAction.IDLE


async def test_climate_off_state(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test climate entity in off state."""
    data = {
        123: {
            "HVAC_STATE": "off",
            "HVAC_MODE": "Off",
            "TEMPERATURE_F": 72.0,
            "HUMIDITY": 50,
            "COOL_SETPOINT_F": 75.0,
            "HEAT_SETPOINT_F": 68.0,
        }
    }

    await _setup_integration_with_data(hass, mock_config_entry, data)

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.OFF
    assert state.attributes["hvac_action"] == HVACAction.OFF
    assert state.attributes["temperature"] is None


async def test_climate_cool_state(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test climate entity in cool state."""
    data = {
        123: {
            "HVAC_STATE": "cooling",
            "HVAC_MODE": "Cool",
            "TEMPERATURE_F": 74.0,
            "HUMIDITY": 55,
            "COOL_SETPOINT_F": 72.0,
            "HEAT_SETPOINT_F": 68.0,
        }
    }

    await _setup_integration_with_data(hass, mock_config_entry, data)

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.COOL
    assert state.attributes["hvac_action"] == HVACAction.COOLING
    assert state.attributes["temperature"] == 72.0


async def test_climate_auto_state(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test climate entity in auto state."""
    data = {
        123: {
            "HVAC_STATE": "heating",
            "HVAC_MODE": "Auto",
            "TEMPERATURE_F": 65.0,
            "HUMIDITY": 40,
            "COOL_SETPOINT_F": 75.0,
            "HEAT_SETPOINT_F": 68.0,
        }
    }

    await _setup_integration_with_data(hass, mock_config_entry, data)

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.HEAT_COOL
    assert state.attributes["hvac_action"] == HVACAction.HEATING
    assert state.attributes["target_temp_high"] == 75.0
    assert state.attributes["target_temp_low"] == 68.0


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode(hass: HomeAssistant) -> None:
    """Test setting HVAC mode."""
    with patch(
        "pyControl4.climate.C4Climate.setHvacMode", new_callable=AsyncMock
    ) as mock_set:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
            blocking=True,
        )
        mock_set.assert_called_once_with("Cool")


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_to_off(hass: HomeAssistant) -> None:
    """Test setting HVAC mode to off."""
    with patch(
        "pyControl4.climate.C4Climate.setHvacMode", new_callable=AsyncMock
    ) as mock_set:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
            blocking=True,
        )
        mock_set.assert_called_once_with("Off")


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_heat_mode(hass: HomeAssistant) -> None:
    """Test setting temperature in heat mode."""
    with patch(
        "pyControl4.climate.C4Climate.setHeatSetpointF", new_callable=AsyncMock
    ) as mock_set:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 70.0},
            blocking=True,
        )
        mock_set.assert_called_once_with(70.0)


async def test_set_temperature_cool_mode(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test setting temperature in cool mode."""
    data = {
        123: {
            "HVAC_STATE": "idle",
            "HVAC_MODE": "Cool",
            "TEMPERATURE_F": 74.0,
            "HUMIDITY": 50,
            "COOL_SETPOINT_F": 72.0,
            "HEAT_SETPOINT_F": 68.0,
        }
    }

    await _setup_integration_with_data(hass, mock_config_entry, data)

    with patch(
        "pyControl4.climate.C4Climate.setCoolSetpointF", new_callable=AsyncMock
    ) as mock_set:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 70.0},
            blocking=True,
        )
        mock_set.assert_called_once_with(70.0)


async def test_set_temperature_range_auto_mode(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test setting temperature range in auto mode."""
    data = {
        123: {
            "HVAC_STATE": "idle",
            "HVAC_MODE": "Auto",
            "TEMPERATURE_F": 70.0,
            "HUMIDITY": 50,
            "COOL_SETPOINT_F": 75.0,
            "HEAT_SETPOINT_F": 68.0,
        }
    }

    await _setup_integration_with_data(hass, mock_config_entry, data)

    with (
        patch(
            "pyControl4.climate.C4Climate.setHeatSetpointF", new_callable=AsyncMock
        ) as mock_heat,
        patch(
            "pyControl4.climate.C4Climate.setCoolSetpointF", new_callable=AsyncMock
        ) as mock_cool,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "target_temp_low": 65.0,
                "target_temp_high": 78.0,
            },
            blocking=True,
        )
        mock_heat.assert_called_once_with(65.0)
        mock_cool.assert_called_once_with(78.0)


async def test_climate_unavailable_when_no_data(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test climate entity is unavailable when coordinator has no data for it."""
    await _setup_integration_with_data(hass, mock_config_entry, {})

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "unavailable"


async def test_climate_missing_variables(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test climate entity handles missing variables gracefully."""
    data = {
        123: {
            "HVAC_STATE": "idle",
            "HVAC_MODE": "Heat",
            # Missing TEMPERATURE_F and HUMIDITY
            "COOL_SETPOINT_F": 75.0,
            "HEAT_SETPOINT_F": 68.0,
        }
    }

    await _setup_integration_with_data(hass, mock_config_entry, data)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes.get("current_temperature") is None
    assert state.attributes.get("current_humidity") is None
    assert state.attributes["temperature"] == 68.0


async def test_climate_unknown_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test climate entity handles unknown HVAC mode."""
    data = {
        123: {
            "HVAC_STATE": "idle",
            "HVAC_MODE": "UnknownMode",
            "TEMPERATURE_F": 72.0,
            "HUMIDITY": 50,
            "COOL_SETPOINT_F": 75.0,
            "HEAT_SETPOINT_F": 68.0,
        }
    }

    await _setup_integration_with_data(hass, mock_config_entry, data)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF  # Defaults to OFF for unknown modes


async def test_climate_unknown_hvac_state(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test climate entity handles unknown HVAC state."""
    data = {
        123: {
            "HVAC_STATE": "unknown_state",
            "HVAC_MODE": "Heat",
            "TEMPERATURE_F": 72.0,
            "HUMIDITY": 50,
            "COOL_SETPOINT_F": 75.0,
            "HEAT_SETPOINT_F": 68.0,
        }
    }

    await _setup_integration_with_data(hass, mock_config_entry, data)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get("hvac_action") is None
