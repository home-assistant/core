"""Tests for the Watts Vision climate platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from visionpluspython.models import ThermostatDevice, ThermostatMode

from homeassistant.components.climate import HVACMode
from homeassistant.components.watts import WattsVisionRuntimeData
from homeassistant.components.watts.climate import WattsVisionClimate, async_setup_entry
from homeassistant.components.watts.coordinator import WattsVisionDeviceCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from tests.common import MockConfigEntry


def create_device_coordinator(device=None):
    """Create a mock device coordinator."""
    coordinator = MagicMock(spec=WattsVisionDeviceCoordinator)
    coordinator.data = device
    coordinator.client = MagicMock()
    coordinator.client.set_thermostat_temperature = AsyncMock()
    coordinator.client.set_thermostat_mode = AsyncMock()
    coordinator.async_refresh = AsyncMock()
    coordinator.trigger_fast_polling = MagicMock()
    coordinator.last_update_success = True
    coordinator.available = device is not None
    return coordinator


@pytest.fixture
def mock_hass():
    """Mock HomeAssistant instance."""
    return MagicMock(spec=HomeAssistant)


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(domain="watts")


@pytest.fixture
def mock_thermostat_device():
    """Mock Watts Vision thermostat device."""
    device = MagicMock(spec=ThermostatDevice)
    device.device_id = "thermostat_123"
    device.device_name = "Test Thermostat"
    device.current_temperature = 20.5
    device.setpoint = 22.0
    device.thermostat_mode = "Comfort"
    device.min_allowed_temperature = 5.0
    device.max_allowed_temperature = 30.0
    device.temperature_unit = "C"
    device.is_online = True
    device.device_type = "thermostat"
    device.room_name = "Living Room"
    device.available_thermostat_modes = [
        "Program",
        "Eco",
        "Comfort",
        "Off",
        "Defrost",
        "Timer",
    ]
    return device


async def test_climate_initialization(mock_thermostat_device) -> None:
    """Test climate entity initialization."""
    coordinator = create_device_coordinator(mock_thermostat_device)
    climate = WattsVisionClimate(coordinator, mock_thermostat_device)

    assert climate._device == mock_thermostat_device
    assert climate._attr_unique_id == "thermostat_123"

    device_info = climate.device_info
    assert device_info is not None
    assert device_info["identifiers"] == {("watts", "thermostat_123")}
    assert device_info["name"] == "Living Room Test Thermostat"
    assert device_info["manufacturer"] == "Watts"
    assert device_info["model"] == "Vision+ thermostat"

    assert climate._attr_min_temp == 5.0
    assert climate._attr_max_temp == 30.0
    assert climate._attr_temperature_unit == UnitOfTemperature.CELSIUS


def test_current_temperature(mock_thermostat_device) -> None:
    """Test current temperature property."""
    coordinator = create_device_coordinator(mock_thermostat_device)
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)
    assert climate_entity.current_temperature == 20.5


def test_target_temperature(mock_thermostat_device) -> None:
    """Test target temperature property."""
    coordinator = create_device_coordinator(mock_thermostat_device)
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)
    assert climate_entity.target_temperature == 22.0


def test_hvac_mode_comfort(mock_thermostat_device) -> None:
    """Test HVAC mode property for Comfort mode."""
    coordinator = create_device_coordinator(mock_thermostat_device)
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)
    assert climate_entity.hvac_mode == HVACMode.HEAT


def test_hvac_mode_eco(mock_thermostat_device) -> None:
    """Test HVAC mode mapping for Eco mode."""
    mock_thermostat_device.thermostat_mode = "Eco"
    coordinator = create_device_coordinator(mock_thermostat_device)
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)
    assert climate_entity.hvac_mode == HVACMode.HEAT


def test_hvac_mode_program(mock_thermostat_device) -> None:
    """Test HVAC mode mapping for Program mode."""
    mock_thermostat_device.thermostat_mode = "Program"
    coordinator = create_device_coordinator(mock_thermostat_device)
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)
    assert climate_entity.hvac_mode == HVACMode.AUTO


def test_hvac_mode_off(mock_thermostat_device) -> None:
    """Test HVAC mode mapping for Off mode."""
    mock_thermostat_device.thermostat_mode = "Off"
    coordinator = create_device_coordinator(mock_thermostat_device)
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)
    assert climate_entity.hvac_mode == HVACMode.OFF


def test_hvac_mode_unknown(mock_thermostat_device) -> None:
    """Test HVAC mode mapping for unknown mode."""
    mock_thermostat_device.thermostat_mode = "Unknown"
    coordinator = create_device_coordinator(mock_thermostat_device)
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)
    assert climate_entity.hvac_mode is None


async def test_async_request_refresh(mock_thermostat_device) -> None:
    """Test async_request_refresh method."""
    coordinator = create_device_coordinator(mock_thermostat_device)
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)

    await climate_entity.async_request_refresh()

    coordinator.async_refresh.assert_called_once()


def test_available_true(mock_thermostat_device) -> None:
    """Test available property when device is online."""
    coordinator = create_device_coordinator(mock_thermostat_device)
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)
    assert climate_entity.available is True


def test_available_false_offline(mock_thermostat_device) -> None:
    """Test available property when device is offline."""
    mock_thermostat_device.is_online = False
    coordinator = create_device_coordinator(mock_thermostat_device)
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)
    assert climate_entity.available is False


async def test_set_temperature_success(mock_thermostat_device) -> None:
    """Test temperature setting success."""
    coordinator = create_device_coordinator(mock_thermostat_device)
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)

    initial_temp = climate_entity.target_temperature
    assert initial_temp == 22.0

    await climate_entity.async_set_temperature(temperature=23.5)
    coordinator.client.set_thermostat_temperature.assert_called_once_with(
        climate_entity.device_id, 23.5
    )
    coordinator.trigger_fast_polling.assert_called_once()
    coordinator.async_refresh.assert_called_once()


async def test_set_temperature_with_attr_temperature(mock_thermostat_device) -> None:
    """Test temperature setting using ATTR_TEMPERATURE."""
    coordinator = create_device_coordinator(mock_thermostat_device)
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)

    await climate_entity.async_set_temperature(**{ATTR_TEMPERATURE: 24.0})
    coordinator.client.set_thermostat_temperature.assert_called_once_with(
        climate_entity.device_id, 24.0
    )
    coordinator.trigger_fast_polling.assert_called_once()
    coordinator.async_refresh.assert_called_once()


async def test_set_temperature_no_temperature(mock_thermostat_device) -> None:
    """Test temperature setting without temperature parameter."""
    coordinator = create_device_coordinator(mock_thermostat_device)
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)

    await climate_entity.async_set_temperature()
    coordinator.client.set_thermostat_temperature.assert_not_called()
    coordinator.trigger_fast_polling.assert_not_called()
    coordinator.async_refresh.assert_not_called()


async def test_set_temperature_error(mock_thermostat_device) -> None:
    """Test temperature setting with API error."""
    coordinator = create_device_coordinator(mock_thermostat_device)
    coordinator.client.set_thermostat_temperature.side_effect = RuntimeError(
        "API Error"
    )
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)

    with pytest.raises(HomeAssistantError, match="Error setting temperature"):
        await climate_entity.async_set_temperature(temperature=23.5)

    coordinator.client.set_thermostat_temperature.assert_called_once_with(
        climate_entity.device_id, 23.5
    )
    coordinator.trigger_fast_polling.assert_not_called()
    coordinator.async_refresh.assert_not_called()


async def test_set_temperature_changes_setpoint(mock_thermostat_device) -> None:
    """Test that setting temperature actually changes the device setpoint."""
    coordinator = create_device_coordinator(mock_thermostat_device)
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)

    assert climate_entity.target_temperature == 22.0

    async def mock_refresh():
        mock_thermostat_device.setpoint = 25.0

    coordinator.async_refresh.side_effect = mock_refresh

    await climate_entity.async_set_temperature(temperature=25.0)

    coordinator.client.set_thermostat_temperature.assert_called_once_with(
        climate_entity.device_id, 25.0
    )
    coordinator.trigger_fast_polling.assert_called_once()
    coordinator.async_refresh.assert_called_once()

    assert climate_entity.target_temperature == 25.0


async def test_set_temperature_no_change_on_api_failure(mock_thermostat_device) -> None:
    """Test that temperature doesn't change when API call fails."""
    coordinator = create_device_coordinator(mock_thermostat_device)
    coordinator.client.set_thermostat_temperature.side_effect = RuntimeError(
        "API Error"
    )
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)

    initial_temp = climate_entity.target_temperature
    assert initial_temp == 22.0

    with pytest.raises(HomeAssistantError, match="Error setting temperature"):
        await climate_entity.async_set_temperature(temperature=25.0)

    coordinator.client.set_thermostat_temperature.assert_called_once_with(
        climate_entity.device_id, 25.0
    )
    coordinator.trigger_fast_polling.assert_not_called()
    coordinator.async_refresh.assert_not_called()

    assert climate_entity.target_temperature == initial_temp


async def test_set_hvac_mode_heat_success(mock_thermostat_device) -> None:
    """Test HVAC mode setting to heat."""
    coordinator = create_device_coordinator(mock_thermostat_device)
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)

    await climate_entity.async_set_hvac_mode(HVACMode.HEAT)
    coordinator.client.set_thermostat_mode.assert_called_once_with(
        climate_entity.device_id, ThermostatMode.COMFORT
    )
    coordinator.trigger_fast_polling.assert_called_once()
    coordinator.async_refresh.assert_called_once()


async def test_set_hvac_mode_off_success(mock_thermostat_device) -> None:
    """Test HVAC mode setting to off."""
    coordinator = create_device_coordinator(mock_thermostat_device)
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)

    await climate_entity.async_set_hvac_mode(HVACMode.OFF)
    coordinator.client.set_thermostat_mode.assert_called_once_with(
        climate_entity.device_id, ThermostatMode.OFF
    )
    coordinator.trigger_fast_polling.assert_called_once()
    coordinator.async_refresh.assert_called_once()


async def test_set_hvac_mode_auto_success(mock_thermostat_device) -> None:
    """Test HVAC mode setting to auto."""
    coordinator = create_device_coordinator(mock_thermostat_device)
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)

    await climate_entity.async_set_hvac_mode(HVACMode.AUTO)
    coordinator.client.set_thermostat_mode.assert_called_once_with(
        climate_entity.device_id, ThermostatMode.PROGRAM
    )
    coordinator.trigger_fast_polling.assert_called_once()
    coordinator.async_refresh.assert_called_once()


async def test_set_hvac_mode_unsupported(mock_thermostat_device) -> None:
    """Test setting unsupported HVAC mode."""
    coordinator = create_device_coordinator(mock_thermostat_device)
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)

    with pytest.raises(KeyError):
        await climate_entity.async_set_hvac_mode(HVACMode.FAN_ONLY)
    coordinator.client.set_thermostat_mode.assert_not_called()
    coordinator.trigger_fast_polling.assert_not_called()
    coordinator.async_refresh.assert_not_called()


async def test_set_hvac_mode_error(mock_thermostat_device) -> None:
    """Test HVAC mode setting with API error."""
    coordinator = create_device_coordinator(mock_thermostat_device)
    coordinator.client.set_thermostat_mode.side_effect = RuntimeError("API Error")
    climate_entity = WattsVisionClimate(coordinator, mock_thermostat_device)

    with pytest.raises(HomeAssistantError, match="Error setting HVAC mode"):
        await climate_entity.async_set_hvac_mode(HVACMode.HEAT)

    coordinator.client.set_thermostat_mode.assert_called_once_with(
        climate_entity.device_id, ThermostatMode.COMFORT
    )
    coordinator.trigger_fast_polling.assert_not_called()
    coordinator.async_refresh.assert_not_called()


async def test_async_setup_entry_with_thermostat_devices(
    mock_hass, mock_config_entry
) -> None:
    """Test setup entry with thermostat devices."""
    async_add_entities = MagicMock(spec=AddEntitiesCallback)

    thermostat_device = MagicMock(spec=ThermostatDevice)
    thermostat_device.device_id = "thermostat_1"
    thermostat_device.device_name = "Test Thermostat 1"
    thermostat_device.current_temperature = 21.0
    thermostat_device.setpoint = 23.0
    thermostat_device.thermostat_mode = "Program"
    thermostat_device.min_allowed_temperature = 5.0
    thermostat_device.max_allowed_temperature = 30.0
    thermostat_device.temperature_unit = "C"
    thermostat_device.is_online = True
    thermostat_device.device_type = "thermostat"
    thermostat_device.room_name = "Bedroom"
    thermostat_device.available_thermostat_modes = ["Program", "Eco", "Comfort", "Off"]

    device_coordinator = create_device_coordinator(thermostat_device)
    device_coordinators = {"thermostat_1": device_coordinator}

    entry = MagicMock(spec=ConfigEntry)
    entry.runtime_data = WattsVisionRuntimeData(
        hub_coordinator=MagicMock(),
        device_coordinators=device_coordinators,
        auth=MagicMock(),
        client=MagicMock(),
    )

    await async_setup_entry(mock_hass, entry, async_add_entities)

    async_add_entities.assert_called_once()
    args = async_add_entities.call_args
    entities = args[0][0]
    assert len(entities) == 1
    assert isinstance(entities[0], WattsVisionClimate)
    assert args[1]["update_before_add"] is True


async def test_async_setup_entry_empty_data(mock_hass, mock_config_entry) -> None:
    """Test setup entry with empty coordinator data."""
    async_add_entities = MagicMock(spec=AddEntitiesCallback)

    entry = MagicMock(spec=ConfigEntry)
    entry.runtime_data = WattsVisionRuntimeData(
        hub_coordinator=MagicMock(),
        device_coordinators={},
        auth=MagicMock(),
        client=MagicMock(),
    )

    await async_setup_entry(mock_hass, entry, async_add_entities)

    # With empty data, async_add_entities is called with empty list
    async_add_entities.assert_called_once_with([], update_before_add=True)


async def test_async_setup_entry_multiple_thermostat_devices(
    mock_hass, mock_config_entry
) -> None:
    """Test setup entry with multiple thermostat devices."""
    async_add_entities = MagicMock(spec=AddEntitiesCallback)

    thermostat1 = MagicMock(spec=ThermostatDevice)
    thermostat1.device_id = "thermostat_1"
    thermostat1.device_name = "Thermostat 1"

    thermostat2 = MagicMock(spec=ThermostatDevice)
    thermostat2.device_id = "thermostat_2"
    thermostat2.device_name = "Thermostat 2"

    device_coordinators = {
        "thermostat_1": create_device_coordinator(thermostat1),
        "thermostat_2": create_device_coordinator(thermostat2),
    }

    entry = MagicMock(spec=ConfigEntry)
    entry.runtime_data = WattsVisionRuntimeData(
        hub_coordinator=MagicMock(),
        device_coordinators=device_coordinators,
        auth=MagicMock(),
        client=MagicMock(),
    )

    await async_setup_entry(mock_hass, entry, async_add_entities)

    async_add_entities.assert_called_once()
    args = async_add_entities.call_args
    entities = args[0][0]
    assert len(entities) == 2
    assert all(isinstance(entity, WattsVisionClimate) for entity in entities)
    assert args[1]["update_before_add"] is True


async def test_async_setup_entry_device_coordinator_no_data(
    mock_hass, mock_config_entry
) -> None:
    """Test setup entry when device coordinator has no data."""
    async_add_entities = MagicMock(spec=AddEntitiesCallback)

    device_coordinator = create_device_coordinator(None)
    device_coordinators = {"thermostat_1": device_coordinator}

    entry = MagicMock(spec=ConfigEntry)
    entry.runtime_data = WattsVisionRuntimeData(
        hub_coordinator=MagicMock(),
        device_coordinators=device_coordinators,
        auth=MagicMock(),
        client=MagicMock(),
    )

    await async_setup_entry(mock_hass, entry, async_add_entities)

    async_add_entities.assert_called_once_with([], update_before_add=True)
