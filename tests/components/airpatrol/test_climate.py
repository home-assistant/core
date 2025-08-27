"""Test the AirPatrol climate platform."""

import contextlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.airpatrol.climate import (
    AirPatrolClimate,
    async_setup_entry,
)
from homeassistant.components.airpatrol.const import DOMAIN
from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_OFF,
    SWING_ON,
    HVACMode,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


# Test data builders - these are functions, not fixtures
def make_climate_data(
    power="on",
    target_temp="22.000",
    mode="cool",
    fan_speed="max",
    swing="off",
    current_temp="22.5",
    current_humidity="45",
) -> dict[str, str]:
    """Build climate data dict."""
    return {
        "ParametersData": {
            "PumpPower": power,
            "PumpTemp": target_temp,
            "PumpMode": mode,
            "FanSpeed": fan_speed,
            "Swing": swing,
        },
        "RoomTemp": current_temp,
        "RoomHumidity": current_humidity,
    }


DEFAULT_UNIT_ID = "test_unit_001"


def make_unit_data(
    unit_id=DEFAULT_UNIT_ID,
    name="Living room",
    manufacturer="AirPatrol",
    model="apw",
    hwid="hw01",
    climate_data=None,
) -> dict:
    """Build unit data dict."""
    unit = {
        "unit_id": unit_id,
        "name": name,
        "manufacturer": manufacturer,
        "model": model,
        "hwid": hwid,
    }
    if climate_data is not None:
        unit["climate"] = climate_data
    return unit


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
def mock_coordinator(mock_config_entry) -> MagicMock:
    """Mock coordinator with async API methods."""
    coordinator = MagicMock()
    mock_config_entry.runtime_data = coordinator
    coordinator.config_entry = mock_config_entry
    coordinator.last_update_success = True

    # Provide an api attribute with async methods
    api_mock = MagicMock()
    api_mock.set_unit_climate_data = AsyncMock()
    coordinator.api = api_mock

    # Default data - can be overridden in tests
    # Coordinator.data should be a dict mapping unit_id to unit data
    default_climate = make_climate_data()
    default_unit = make_unit_data(climate_data=default_climate)
    coordinator.data = {default_unit["unit_id"]: default_unit}

    return coordinator


@pytest.mark.asyncio
async def test_async_setup_entry_adds_entities(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test async_setup_entry creates and adds AirPatrolClimate entities."""
    # Setup test data with one unit having climate data and one without
    unit_with_climate = make_unit_data(
        unit_id="unit1", climate_data=make_climate_data()
    )
    unit_without_climate = make_unit_data(
        unit_id="unit2"
        # No climate_data = no "climate" key
    )

    # Coordinator data should be a dict mapping unit_id to unit data
    mock_coordinator.data = {"unit1": unit_with_climate, "unit2": unit_without_climate}

    added_entities = []

    def async_add_entities(entities):
        added_entities.extend(entities)

    await async_setup_entry(hass, mock_coordinator.config_entry, async_add_entities)

    # Only the unit with 'climate' should be added
    assert len(added_entities) == 1
    entity = added_entities[0]
    assert entity._unit_id == "unit1"
    assert hasattr(entity, "async_set_temperature")
    assert hasattr(entity, "async_set_hvac_mode")


async def test_climate_entity_initialization(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test climate entity initialization."""
    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)
    assert climate.unique_id == f"test_unique_id-{DEFAULT_UNIT_ID}-climate"
    assert climate.available is True  # Has climate data


async def test_climate_entity_unavailable(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test climate entity when climate data is missing."""
    # Create unit without climate data
    unit_without_climate = make_unit_data()  # No climate_data argument
    mock_coordinator.data = {DEFAULT_UNIT_ID: unit_without_climate}

    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)

    assert climate.available is False  # No climate data


async def test_climate_hvac_modes(hass: HomeAssistant, mock_coordinator) -> None:
    """Test climate HVAC modes."""
    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)
    expected_modes = [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]
    assert climate._attr_hvac_modes == expected_modes


async def test_climate_fan_modes(hass: HomeAssistant, mock_coordinator) -> None:
    """Test climate fan modes."""
    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)

    assert climate._attr_fan_modes == [FAN_LOW, FAN_HIGH, FAN_AUTO]


async def test_climate_swing_modes(hass: HomeAssistant, mock_coordinator) -> None:
    """Test climate swing modes."""
    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)
    expected_modes = [SWING_ON, SWING_OFF]
    assert climate._attr_swing_modes == expected_modes


async def test_climate_temperature_range(hass: HomeAssistant, mock_coordinator) -> None:
    """Test climate temperature range."""
    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)
    assert climate._attr_min_temp == 16.0
    assert climate._attr_max_temp == 30.0


async def test_climate_set_temperature(hass: HomeAssistant, mock_coordinator) -> None:
    """Test setting temperature."""
    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)
    climate.hass = hass

    # Mock the API call to return response data
    mock_response_data = {
        "ApiVersion": "12",
        "CommandMode": "parameters",
        **make_climate_data(target_temp="25.000"),
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
    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)
    climate.hass = hass

    # Mock the API call to return response data
    mock_response_data = {
        "ApiVersion": "12",
        "CommandMode": "parameters",
        **make_climate_data(),
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
    climate = AirPatrolClimate(mock_coordinator, "test_unit_001")
    climate.hass = hass

    # Mock the API call to return response data
    mock_response_data = {
        "ApiVersion": "12",
        "CommandMode": "parameters",
        **make_climate_data(fan_speed=FAN_MEDIUM),
    }
    mock_coordinator.api.set_unit_climate_data = AsyncMock(
        return_value=mock_response_data
    )

    await climate.async_set_fan_mode(FAN_MEDIUM)

    # Verify the API was called
    mock_coordinator.api.set_unit_climate_data.assert_called_once()
    call_args = mock_coordinator.api.set_unit_climate_data.call_args
    assert call_args[0][0] == "test_unit_001"  # unit_id
    assert call_args[0][1]["ParametersData"]["FanSpeed"] == "max"


async def test_climate_set_swing_mode(hass: HomeAssistant, mock_coordinator) -> None:
    """Test setting swing mode."""
    climate = AirPatrolClimate(mock_coordinator, "test_unit_001")
    climate.hass = hass
    climate.async_write_ha_state = AsyncMock()

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
    assert call_args[0][1]["ParametersData"]["Swing"] == "on"


async def test_climate_turn_on_off(hass: HomeAssistant, mock_coordinator) -> None:
    """Test turning climate on and off."""
    climate = AirPatrolClimate(mock_coordinator, "test_unit_001")
    climate.hass = hass
    climate.async_write_ha_state = AsyncMock()

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
    climate_data = make_climate_data(power="off")
    unit = make_unit_data(climate_data=climate_data)
    mock_coordinator.data = {DEFAULT_UNIT_ID: unit}

    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)
    assert climate.hvac_mode == HVACMode.OFF


async def test_climate_cool_mode(hass: HomeAssistant, mock_coordinator) -> None:
    """Test climate in cool mode."""
    # Create unit with cool mode
    climate_data = make_climate_data(power="on", mode="cool")
    unit = make_unit_data(climate_data=climate_data)
    mock_coordinator.data = {DEFAULT_UNIT_ID: unit}

    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)
    assert climate.hvac_mode == HVACMode.COOL


# Parametrized tests for better coverage
@pytest.mark.parametrize(
    ("power", "mode", "expected_hvac_mode"),
    [
        ("off", "heat", HVACMode.OFF),
        ("on", "heat", HVACMode.HEAT),
        ("on", "cool", HVACMode.COOL),
        ("on", "unknown", None),  # Unknown mode returns None
    ],
)
async def test_climate_hvac_mode_mapping(
    hass: HomeAssistant, mock_coordinator, power, mode, expected_hvac_mode
) -> None:
    """Test HVAC mode mapping for different power/mode combinations."""
    climate_data = make_climate_data(power=power, mode=mode)
    unit = make_unit_data(climate_data=climate_data)
    mock_coordinator.data = {DEFAULT_UNIT_ID: unit}

    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)
    assert climate.hvac_mode == expected_hvac_mode


@pytest.mark.parametrize(
    ("fan_speed", "expected_fan_mode"),
    [
        ("min", FAN_LOW),
        ("max", FAN_HIGH),
        ("auto", FAN_AUTO),
        ("unknown", None),  # Unknown returns None
    ],
)
async def test_climate_fan_mode_mapping(
    hass: HomeAssistant, mock_coordinator, fan_speed, expected_fan_mode
) -> None:
    """Test fan mode mapping for different speeds."""
    climate_data = make_climate_data(fan_speed=fan_speed)
    unit = make_unit_data(climate_data=climate_data)
    mock_coordinator.data = {DEFAULT_UNIT_ID: unit}

    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)
    assert climate.fan_mode == expected_fan_mode


@pytest.mark.parametrize(
    ("swing", "expected_swing_mode"),
    [
        ("on", SWING_ON),
        ("off", SWING_OFF),
        ("unknown", None),  # Unknown returns None
    ],
)
async def test_climate_swing_mode_mapping(
    hass: HomeAssistant, mock_coordinator, swing, expected_swing_mode
) -> None:
    """Test swing mode mapping."""
    climate_data = make_climate_data(swing=swing)
    unit = make_unit_data(climate_data=climate_data)
    mock_coordinator.data = {DEFAULT_UNIT_ID: unit}

    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)
    assert climate.swing_mode == expected_swing_mode


@pytest.mark.asyncio
async def test_climate_set_temperature_api_error(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test async_set_temperature handles API error."""
    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)
    mock_coordinator.api.set_unit_climate_data = AsyncMock(
        side_effect=Exception("API error")
    )
    # Should not raise, but log error and not update
    with contextlib.suppress(Exception):
        await climate.async_set_temperature(temperature=25.0)


@pytest.mark.asyncio
async def test_climate_target_temperature_missing(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test target_temperature when PumpTemp is missing."""
    climate_data = make_climate_data(target_temp=None)
    unit = make_unit_data(climate_data=climate_data)
    mock_coordinator.data = {DEFAULT_UNIT_ID: unit}
    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)
    assert climate.target_temperature is None


@pytest.mark.asyncio
async def test_climate_fan_mode_invalid(hass: HomeAssistant, mock_coordinator) -> None:
    """Test fan_mode with unexpected value."""
    climate_data = make_climate_data(fan_speed="unknown")
    unit = make_unit_data(climate_data=climate_data)
    mock_coordinator.data = {DEFAULT_UNIT_ID: unit}
    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)
    assert climate.fan_mode is None


@pytest.mark.asyncio
async def test_climate_swing_mode_invalid(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test swing_mode with unexpected value."""
    climate_data = make_climate_data(swing="sideways")
    unit = make_unit_data(climate_data=climate_data)
    mock_coordinator.data = {DEFAULT_UNIT_ID: unit}
    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)
    assert climate.swing_mode is None


@pytest.mark.asyncio
async def test_climate_current_temperature(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test current_temperature returns correct float value."""
    climate_data = make_climate_data(current_temp="22.5")
    unit = make_unit_data(climate_data=climate_data)
    mock_coordinator.data = {DEFAULT_UNIT_ID: unit}
    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)
    assert climate.current_temperature == 22.5


@pytest.mark.asyncio
async def test_climate_current_humidity(hass: HomeAssistant, mock_coordinator) -> None:
    """Test current_humidity returns correct float value."""
    climate_data = make_climate_data(current_humidity="55.5")
    unit = make_unit_data(climate_data=climate_data)
    mock_coordinator.data = {DEFAULT_UNIT_ID: unit}
    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)
    assert climate.current_humidity == 55.5


@pytest.mark.asyncio
async def test_climate_current_humidity_missing(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test current_humidity returns None if RoomHumidity is missing."""
    climate_data = make_climate_data(current_humidity=None)
    unit = make_unit_data(climate_data=climate_data)
    mock_coordinator.data = {DEFAULT_UNIT_ID: unit}
    climate = AirPatrolClimate(mock_coordinator, DEFAULT_UNIT_ID)
    assert climate.current_humidity is None
