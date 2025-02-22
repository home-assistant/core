"""Test the Wolf SmartSet Service Sensor platform."""

from unittest.mock import MagicMock

import pytest
from wolf_comm import EnergyParameter, PowerParameter

from homeassistant.components.wolflink.const import (
    COORDINATOR,
    DEVICE_ID,
    DOMAIN,
    MANUFACTURER,
    PARAMETERS,
)
from homeassistant.components.wolflink.sensor import (
    WolfLinkEnergy,
    WolfLinkHours,
    WolfLinkPercentage,
    WolfLinkPower,
    WolfLinkPressure,
    WolfLinkSensor,
    WolfLinkTemperature,
    async_setup_entry,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONFIG

from tests.common import MockConfigEntry


@pytest.fixture
def mock_coordinator(hass: HomeAssistant) -> MagicMock:
    """Mock the Wolf SmartSet Service Coordinator."""
    coordinator = MagicMock()
    coordinator.data = {}
    hass.data[DOMAIN] = {CONFIG[DEVICE_ID]: {COORDINATOR: coordinator}}
    return coordinator


async def mock_config_entry(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test already configured while creating entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=CONFIG[DEVICE_ID], data=CONFIG
    )
    config_entry.add_to_hass(hass)

    device_id = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, CONFIG[DEVICE_ID])},
        configuration_url="https://www.wolf-smartset.com/",
        manufacturer=MANUFACTURER,
    ).id
    assert device_registry.async_get(device_id).identifiers == {(DOMAIN, "1234")}


def test_wolflink_sensor_native_value(mock_coordinator: MagicMock) -> None:
    """Test WolflinkSensor native value."""
    parameter = MagicMock()
    parameter.parameter_id = "outside_temp"
    sensor = WolfLinkSensor(mock_coordinator, parameter, "mock_device_id")
    mock_coordinator.data = {"outside_temp": [None, 20]}
    assert sensor.native_value == 20


def test_wolflink_sensor_extra_state_attributes(mock_coordinator: MagicMock) -> None:
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


def test_wolflink_temperature_initialization(mock_coordinator: MagicMock) -> None:
    """Test WolflinkTemperature initialization."""
    parameter = MagicMock()
    parameter.name = "Outside Temperature"
    parameter.parameter_id = "outside_temp"
    sensor = WolfLinkTemperature(mock_coordinator, parameter, "mock_device_id")
    assert sensor._attr_device_class == "temperature"
    assert sensor._attr_native_unit_of_measurement == UnitOfTemperature.CELSIUS


def test_wolflink_pressure_initialization(mock_coordinator: MagicMock) -> None:
    """Test WolflinkPressure initialization."""
    parameter = MagicMock()
    parameter.name = "Pressure"
    parameter.parameter_id = "pressure"
    sensor = WolfLinkPressure(mock_coordinator, parameter, "mock_device_id")
    assert sensor._attr_device_class == "pressure"
    assert sensor._attr_native_unit_of_measurement == UnitOfPressure.BAR


def test_wolflink_power_initialization(mock_coordinator: MagicMock) -> None:
    """Test WolflinkPower initialization."""
    parameter = MagicMock()
    parameter.name = "Power"
    parameter.parameter_id = "power"
    sensor = WolfLinkPower(mock_coordinator, parameter, "mock_device_id")
    assert sensor._attr_device_class == "power"
    assert sensor._attr_native_unit_of_measurement == UnitOfPower.KILO_WATT


def test_wolflink_energy_initialization(mock_coordinator: MagicMock) -> None:
    """Test WolflinkEnergy initialization."""
    parameter = MagicMock()
    parameter.name = "Energy"
    parameter.parameter_id = "energy"
    sensor = WolfLinkEnergy(mock_coordinator, parameter, "mock_device_id")
    assert sensor._attr_device_class == "energy"
    assert sensor._attr_native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR


def test_wolflink_percentage_initialization(mock_coordinator: MagicMock) -> None:
    """Test WolflinkPercentage initialization."""
    parameter = MagicMock()
    parameter.name = "Percentage"
    parameter.parameter_id = "percentage"
    parameter.unit = PERCENTAGE
    sensor = WolfLinkPercentage(mock_coordinator, parameter, "mock_device_id")
    assert sensor.native_unit_of_measurement == PERCENTAGE


def test_wolflink_hours_initialization(mock_coordinator: MagicMock) -> None:
    """Test WolflinkHours initialization."""
    parameter = MagicMock()
    parameter.name = "Hours"
    parameter.parameter_id = "hours"
    sensor = WolfLinkHours(mock_coordinator, parameter, "mock_device_id")
    assert sensor._attr_icon == "mdi:clock"
    assert sensor._attr_native_unit_of_measurement == UnitOfTime.HOURS


async def test_async_setup_entry_wolflink_energy(
    hass: HomeAssistant, mock_coordinator: MagicMock
) -> None:
    """Test async_setup_entry for WolfLinkEnergy."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=str(CONFIG[DEVICE_ID]), data=CONFIG
    )
    config_entry.add_to_hass(hass)

    parameter = MagicMock(spec=EnergyParameter)
    parameter.parameter_id = "energy_param"
    parameter.name = "Energy"
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        PARAMETERS: [parameter],
        COORDINATOR: mock_coordinator,
        DEVICE_ID: "mock_device_id",
    }
    async_add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, async_add_entities)

    assert async_add_entities.call_count == 1
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 1
    assert isinstance(entities[0], WolfLinkEnergy)


async def test_async_setup_entry_wolflink_power(
    hass: HomeAssistant, mock_coordinator: MagicMock
) -> None:
    """Test async_setup_entry for WolfLinkPower."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=str(CONFIG[DEVICE_ID]), data=CONFIG
    )
    config_entry.add_to_hass(hass)

    parameter = MagicMock(spec=PowerParameter)
    parameter.parameter_id = "power_param"
    parameter.name = "Power"
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        PARAMETERS: [parameter],
        COORDINATOR: mock_coordinator,
        DEVICE_ID: "mock_device_id",
    }
    async_add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, async_add_entities)

    assert async_add_entities.call_count == 1
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 1
    assert isinstance(entities[0], WolfLinkPower)
