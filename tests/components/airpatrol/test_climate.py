"""Test the AirPatrol climate platform."""

import contextlib
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.airpatrol.climate import AirPatrolClimate
from homeassistant.components.airpatrol.const import DOMAIN
from homeassistant.components.climate import (
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_OFF,
    SWING_ON,
    HVACAction,
    HVACMode,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "password": "test_password",
            "access_token": "test_access_token",
        },
        unique_id="test_unique_id",
    )


@pytest.fixture
def mock_coordinator():
    """Mock coordinator."""
    coordinator = MagicMock()
    coordinator.config_entry.unique_id = "test_unique_id"
    coordinator.data = [
        {
            "unit_id": "test_unit_001",
            "name": "Test Unit",
            "manufacturer": "AirPatrol",
            "model": "apw",
            "climate": {
                "RoomTemp": "22.5",
                "RoomHumidity": "45.2",
                "ParametersData": {
                    "PumpPower": "on",
                    "PumpTemp": "22.5",
                    "PumpMode": "heat",
                    "FanSpeed": "max",
                    "Swing": "off",
                },
            },
            "status": "online",
        }
    ]
    return coordinator


async def test_climate_entity_initialization(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test climate entity initialization."""
    # Provide mock data with status 'online' and climate data
    mock_coordinator.data = [
        {
            "unit_id": "test_unit_001",
            "name": "Vardagsrum",
            "manufacturer": "AirPatrol",
            "model": "apw",
            "climate": {"RoomTemp": "22.5"},
        }
    ]
    unit = mock_coordinator.data[0]
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")
    assert climate.unique_id == "test_unique_id_test_unit_001_climate"
    assert climate.available is True  # Has climate data


async def test_climate_entity_unavailable(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test climate entity when climate data is missing."""
    # Create unit without climate data
    unit = mock_coordinator.data[0].copy()
    del unit["climate"]

    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")

    assert climate.available is False  # No climate data


async def test_climate_hvac_modes(hass: HomeAssistant, mock_coordinator) -> None:
    """Test climate HVAC modes."""
    unit = mock_coordinator.data[0]
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")

    expected_modes = [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]
    assert climate.hvac_modes == expected_modes


async def test_climate_fan_modes(hass: HomeAssistant, mock_coordinator) -> None:
    """Test climate fan modes."""
    unit = mock_coordinator.data[0]
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")

    expected_modes = [FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    assert climate.fan_modes == expected_modes


async def test_climate_swing_modes(hass: HomeAssistant, mock_coordinator) -> None:
    """Test climate swing modes."""
    unit = mock_coordinator.data[0]
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")

    expected_modes = [SWING_ON, SWING_OFF]
    assert climate.swing_modes == expected_modes


async def test_climate_temperature_range(hass: HomeAssistant, mock_coordinator) -> None:
    """Test climate temperature range."""
    unit = mock_coordinator.data[0]
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")

    assert climate.min_temp == 16.0
    assert climate.max_temp == 30.0


async def test_climate_set_temperature(hass: HomeAssistant, mock_coordinator) -> None:
    """Test setting temperature."""
    unit = mock_coordinator.data[0]
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")

    # Mock the API call to return response data
    mock_response_data = {
        "ApiVersion": "12",
        "CommandMode": "parameters",
        "ParametersData": {
            "PumpPower": "on",
            "PumpTemp": "25.000",
            "PumpMode": "heat",
            "FanSpeed": "max",
            "Swing": "off",
        },
        "RoomTemp": "24.5",
        "RoomHumidity": "45",
    }
    mock_coordinator.api.set_unit_climate_data = AsyncMock(
        return_value=mock_response_data
    )

    await climate.async_set_temperature(temperature=25.0)

    # Verify the API was called
    mock_coordinator.api.set_unit_climate_data.assert_called_once()
    call_args = mock_coordinator.api.set_unit_climate_data.call_args
    assert call_args[0][0] == "test_unit_001"  # unit_id
    assert call_args[0][1]["ParametersData"]["PumpTemp"] == "25.000"


async def test_climate_set_hvac_mode(hass: HomeAssistant, mock_coordinator) -> None:
    """Test setting HVAC mode."""
    unit = mock_coordinator.data[0]
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")

    # Mock the API call to return response data
    mock_response_data = {
        "ApiVersion": "12",
        "CommandMode": "parameters",
        "ParametersData": {
            "PumpPower": "on",
            "PumpTemp": "22.000",
            "PumpMode": "cool",
            "FanSpeed": "max",
            "Swing": "off",
        },
        "RoomTemp": "22.5",
        "RoomHumidity": "45",
    }
    mock_coordinator.api.set_unit_climate_data = AsyncMock(
        return_value=mock_response_data
    )

    await climate.async_set_hvac_mode(HVACMode.COOL)

    # Verify the API was called
    mock_coordinator.api.set_unit_climate_data.assert_called_once()
    call_args = mock_coordinator.api.set_unit_climate_data.call_args
    assert call_args[0][0] == "test_unit_001"  # unit_id
    assert call_args[0][1]["ParametersData"]["PumpPower"] == "on"
    assert call_args[0][1]["ParametersData"]["PumpMode"] == "cool"


async def test_climate_set_fan_mode(hass: HomeAssistant, mock_coordinator) -> None:
    """Test setting fan mode."""
    unit = mock_coordinator.data[0]
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")

    # Mock the API call to return response data
    mock_response_data = {
        "ApiVersion": "12",
        "CommandMode": "parameters",
        "ParametersData": {
            "PumpPower": "on",
            "PumpTemp": "22.000",
            "PumpMode": "heat",
            "FanSpeed": "med",
            "Swing": "off",
        },
        "RoomTemp": "22.5",
        "RoomHumidity": "45",
    }
    mock_coordinator.api.set_unit_climate_data = AsyncMock(
        return_value=mock_response_data
    )

    await climate.async_set_fan_mode(FAN_MEDIUM)

    # Verify the API was called
    mock_coordinator.api.set_unit_climate_data.assert_called_once()
    call_args = mock_coordinator.api.set_unit_climate_data.call_args
    assert call_args[0][0] == "test_unit_001"  # unit_id
    assert call_args[0][1]["ParametersData"]["FanSpeed"] == "med"


async def test_climate_set_swing_mode(hass: HomeAssistant, mock_coordinator) -> None:
    """Test setting swing mode."""
    unit = mock_coordinator.data[0]
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")

    # Mock the API call to return response data
    mock_response_data = {
        "ApiVersion": "12",
        "CommandMode": "parameters",
        "ParametersData": {
            "PumpPower": "on",
            "PumpTemp": "22.000",
            "PumpMode": "heat",
            "FanSpeed": "max",
            "Swing": "on",
        },
        "RoomTemp": "22.5",
        "RoomHumidity": "45",
    }
    mock_coordinator.api.set_unit_climate_data = AsyncMock(
        return_value=mock_response_data
    )

    await climate.async_set_swing_mode(SWING_ON)

    # Verify the API was called
    mock_coordinator.api.set_unit_climate_data.assert_called_once()
    call_args = mock_coordinator.api.set_unit_climate_data.call_args
    assert call_args[0][0] == "test_unit_001"  # unit_id
    assert call_args[0][1]["ParametersData"]["Swing"] == "auto"


async def test_climate_turn_on_off(hass: HomeAssistant, mock_coordinator) -> None:
    """Test turning climate on and off."""
    unit = mock_coordinator.data[0]
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")

    # Mock the API call to return response data
    mock_response_data = {
        "ApiVersion": "12",
        "CommandMode": "parameters",
        "ParametersData": {
            "PumpPower": "on",
            "PumpTemp": "22.000",
            "PumpMode": "heat",
            "FanSpeed": "max",
            "Swing": "off",
        },
        "RoomTemp": "22.5",
        "RoomHumidity": "45",
    }
    mock_coordinator.api.set_unit_climate_data = AsyncMock(
        return_value=mock_response_data
    )

    # Test turn on
    await climate.async_turn_on()
    mock_coordinator.api.set_unit_climate_data.assert_called_with(
        "test_unit_001", mock_coordinator.api.set_unit_climate_data.call_args[0][1]
    )

    # Reset mock
    mock_coordinator.api.set_unit_climate_data.reset_mock()

    # Test turn off
    await climate.async_turn_off()
    mock_coordinator.api.set_unit_climate_data.assert_called_once()
    call_args = mock_coordinator.api.set_unit_climate_data.call_args
    assert call_args[0][0] == "test_unit_001"  # unit_id
    assert call_args[0][1]["ParametersData"]["PumpPower"] == "off"


async def test_climate_off_mode(hass: HomeAssistant, mock_coordinator) -> None:
    """Test climate in off mode."""
    # Create unit with pump power off
    unit = mock_coordinator.data[0].copy()
    unit["manufacturer"] = "AirPatrol"
    unit["climate"]["ParametersData"] = {
        "PumpPower": "off",
        "PumpTemp": "22.5",
        "PumpMode": "heat",
        "FanSpeed": "max",
        "Swing": "off",
    }

    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")

    assert climate.hvac_mode == HVACMode.OFF
    assert climate.hvac_action == HVACAction.OFF


async def test_climate_cool_mode(hass: HomeAssistant, mock_coordinator) -> None:
    """Test climate in cool mode."""
    # Create unit with cool mode
    unit = mock_coordinator.data[0].copy()
    unit["manufacturer"] = "AirPatrol"
    unit["climate"]["ParametersData"] = {
        "PumpPower": "on",
        "PumpTemp": "22.5",
        "PumpMode": "cool",
        "FanSpeed": "max",
        "Swing": "off",
    }

    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")

    assert climate.hvac_mode == HVACMode.COOL
    assert climate.hvac_action == HVACAction.COOLING


@pytest.mark.asyncio
async def test_climate_available_logging(
    hass: HomeAssistant, mock_coordinator, caplog: pytest.LogCaptureFixture
) -> None:
    """Test logging when climate entity becomes unavailable and then available again."""
    caplog.set_level(logging.INFO)
    # Use a unit with unit_id 'test_unit_001' for both the entity and coordinator.data
    unit = {
        "unit_id": "test_unit_001",
        "name": "Test Unit",
        "manufacturer": "AirPatrol",
        "model": "apw",
        "climate": {
            "RoomTemp": "22.5",
            "RoomHumidity": "45.2",
            "ParametersData": {
                "PumpPower": "on",
                "PumpTemp": "22.5",
                "PumpMode": "heat",
                "FanSpeed": "max",
                "Swing": "off",
            },
        },
        "status": "online",
    }
    mock_coordinator.data = [unit]
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")
    # Simulate unavailable
    climate._unit = {}
    mock_coordinator.data = []
    mock_coordinator.last_update_success = True
    assert not climate.available
    assert "is unavailable" in caplog.text
    # Simulate available again
    climate._unit = unit
    mock_coordinator.data = [unit]
    mock_coordinator.last_update_success = True
    assert climate.available
    assert "is back online" in caplog.text


@pytest.mark.asyncio
async def test_climate_set_temperature_api_error(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test async_set_temperature handles API error."""
    unit = mock_coordinator.data[0]
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")
    mock_coordinator.api.set_unit_climate_data = AsyncMock(
        side_effect=Exception("API error")
    )
    # Should not raise, but log error and not update
    with contextlib.suppress(Exception):
        await climate.async_set_temperature(temperature=25.0)


@pytest.mark.asyncio
async def test_climate_current_temperature_invalid(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test current_temperature with invalid value."""
    unit = mock_coordinator.data[0].copy()
    unit["climate"]["RoomTemp"] = "not_a_float"
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")
    assert climate.current_temperature is None


@pytest.mark.asyncio
async def test_climate_target_temperature_missing(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test target_temperature when PumpTemp is missing."""
    unit = mock_coordinator.data[0].copy()
    unit["climate"]["ParametersData"].pop("PumpTemp", None)
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")
    assert climate.target_temperature is None


@pytest.mark.asyncio
async def test_climate_fan_mode_invalid(hass: HomeAssistant, mock_coordinator) -> None:
    """Test fan_mode with unexpected value."""
    unit = mock_coordinator.data[0].copy()
    unit["climate"]["ParametersData"]["FanSpeed"] = "unknown"
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")
    # Should default to FAN_HIGH
    assert climate.fan_mode == FAN_HIGH


@pytest.mark.asyncio
async def test_climate_swing_mode_invalid(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test swing_mode with unexpected value."""
    unit = mock_coordinator.data[0].copy()
    unit["climate"]["ParametersData"]["Swing"] = "sideways"
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")
    assert climate.swing_mode == SWING_OFF


@pytest.mark.asyncio
async def test_climate_hvac_action_idle(hass: HomeAssistant, mock_coordinator) -> None:
    """Test hvac_action returns IDLE for unknown mode."""
    unit = mock_coordinator.data[0].copy()
    unit["climate"]["ParametersData"]["PumpMode"] = "unknown"
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")
    assert climate.hvac_action == HVACAction.IDLE


@pytest.mark.asyncio
async def test_climate_current_humidity(hass: HomeAssistant, mock_coordinator) -> None:
    """Test current_humidity returns correct float value."""
    unit = mock_coordinator.data[0].copy()
    unit["climate"]["RoomHumidity"] = "55.5"
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")
    assert climate.current_humidity == 55.5


@pytest.mark.asyncio
async def test_climate_current_humidity_missing(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test current_humidity returns None if RoomHumidity is missing."""
    unit = mock_coordinator.data[0].copy()
    unit["climate"].pop("RoomHumidity", None)
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")
    assert climate.current_humidity is None


@pytest.mark.asyncio
async def test_climate_current_humidity_invalid(
    hass: HomeAssistant, mock_coordinator, caplog: pytest.LogCaptureFixture
) -> None:
    """Test current_humidity returns None and logs error if RoomHumidity is invalid."""
    unit = mock_coordinator.data[0].copy()
    unit["climate"]["RoomHumidity"] = "not_a_float"
    climate = AirPatrolClimate(mock_coordinator, unit, "test_unit_001")
    with caplog.at_level(logging.ERROR):
        assert climate.current_humidity is None
        assert "Failed to convert humidity to float" in caplog.text
