"""Tests for the Wolflink sensor platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.wolflink.const import (
    COORDINATOR,
    DEVICE_ID,
    DOMAIN,
    PARAMETERS,
)
from homeassistant.components.wolflink.sensor import (
    WolfLinkEnergy,
    WolfLinkHours,
    WolfLinkPercentage,
    WolfLinkPower,
    WolfLinkPressure,
    WolfLinkSensor,
    WolfLinkState,
    WolfLinkTemperature,
    async_setup_entry,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@pytest.fixture
def mock_coordinator() -> DataUpdateCoordinator:
    """Mock the data update coordinator."""
    return DataUpdateCoordinator(
        hass=None,
        logger=None,
        name="Wolf",
        update_method=None,
        update_interval=None,
    )


@pytest.fixture
def mock_config_entry() -> ConfigEntry:
    """Mock the config entry."""
    return ConfigEntry(
        entry_id="test",
        domain=DOMAIN,
        data={},
        title="Mock Title",
    )


@pytest.fixture
def mock_hass() -> HomeAssistant:
    """Mock Home Assistant instance."""
    return HomeAssistant()


@pytest.fixture
def mock_add_entities() -> AddConfigEntryEntitiesCallback:
    """Mock add entities callback."""
    return MagicMock()


async def test_async_setup_entry(
    mock_hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_add_entities: AddConfigEntryEntitiesCallback,
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test async setup entry."""
    mock_hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                COORDINATOR: mock_coordinator,
                PARAMETERS: [],
                DEVICE_ID: "mock_device_id",
            }
        }
    }
    await async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)
    assert mock_add_entities.call_count == 1


def test_wolflink_sensor_initialization(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test WolflinkSensor initialization."""
    parameter = MagicMock()
    parameter.name = "Outside Temperature"
    parameter.parameter_id = "outside_temp"
    sensor = WolfLinkSensor(mock_coordinator, parameter, "mock_device_id")
    assert sensor._attr_name == "Outside Temperature"
    assert sensor._attr_unique_id == "mock_device_id:outside_temp"


def test_wolflink_sensor_native_value(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test WolflinkSensor native value."""
    parameter = MagicMock()
    parameter.parameter_id = "outside_temp"
    sensor = WolfLinkSensor(mock_coordinator, parameter, "mock_device_id")
    mock_coordinator.data = {"outside_temp": [None, 20]}
    assert sensor.native_value == 20


def test_wolflink_sensor_extra_state_attributes(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test WolflinkSensor extra state attributes."""
    parameter = MagicMock()
    parameter.parameter_id = "outside_temp"
    parameter.value_id = "value_id"
    parameter.parent = "parent"
    sensor = WolfLinkSensor(mock_coordinator, parameter, "mock_device_id")
    attributes = sensor.extra_state_attributes
    assert attributes["parameter_id"] == "outside_temp"
    assert attributes["value_id"] == "value_id"
    assert attributes["parent"] == "parent"


def test_wolflink_temperature_initialization(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test WolflinkTemperature initialization."""
    parameter = MagicMock()
    parameter.name = "Outside Temperature"
    parameter.parameter_id = "outside_temp"
    sensor = WolfLinkTemperature(mock_coordinator, parameter, "mock_device_id")
    assert sensor._attr_device_class == "temperature"
    assert sensor._attr_native_unit_of_measurement == UnitOfTemperature.CELSIUS


def test_wolflink_pressure_initialization(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test WolflinkPressure initialization."""
    parameter = MagicMock()
    parameter.name = "Pressure"
    parameter.parameter_id = "pressure"
    sensor = WolfLinkPressure(mock_coordinator, parameter, "mock_device_id")
    assert sensor._attr_device_class == "pressure"
    assert sensor._attr_native_unit_of_measurement == UnitOfPressure.BAR


def test_wolflink_power_initialization(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test WolflinkPower initialization."""
    parameter = MagicMock()
    parameter.name = "Power"
    parameter.parameter_id = "power"
    sensor = WolfLinkPower(mock_coordinator, parameter, "mock_device_id")
    assert sensor._attr_device_class == "power"
    assert sensor._attr_native_unit_of_measurement == UnitOfPower.KILO_WATT


def test_wolflink_energy_initialization(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test WolflinkEnergy initialization."""
    parameter = MagicMock()
    parameter.name = "Energy"
    parameter.parameter_id = "energy"
    sensor = WolfLinkEnergy(mock_coordinator, parameter, "mock_device_id")
    assert sensor._attr_device_class == "energy"
    assert sensor._attr_native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR


def test_wolflink_percentage_initialization(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test WolflinkPercentage initialization."""
    parameter = MagicMock()
    parameter.name = "Percentage"
    parameter.parameter_id = "percentage"
    parameter.unit = PERCENTAGE
    sensor = WolfLinkPercentage(mock_coordinator, parameter, "mock_device_id")
    assert sensor.native_unit_of_measurement == PERCENTAGE


def test_wolflink_state_initialization(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test WolflinkState initialization."""
    parameter = MagicMock()
    parameter.name = "State"
    parameter.parameter_id = "state"
    parameter.items = [MagicMock(value=1, name="On"), MagicMock(value=0, name="Off")]
    sensor = WolfLinkState(mock_coordinator, parameter, "mock_device_id")
    mock_coordinator.data = {"state": [None, 1]}
    assert sensor.native_value == "On"


def test_wolflink_hours_initialization(
    mock_coordinator: DataUpdateCoordinator,
) -> None:
    """Test WolflinkHours initialization."""
    parameter = MagicMock()
    parameter.name = "Hours"
    parameter.parameter_id = "hours"
    sensor = WolfLinkHours(mock_coordinator, parameter, "mock_device_id")
    assert sensor._attr_icon == "mdi:clock"
    assert sensor._attr_native_unit_of_measurement == UnitOfTime.HOURS
