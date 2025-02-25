"""Test the Wolf SmartSet Service Sensor platform."""

from unittest.mock import MagicMock

import pytest
from wolf_comm import (
    PERCENTAGE,
    EnergyParameter,
    HoursParameter,
    Parameter,
    PercentageParameter,
    PowerParameter,
    Pressure,
    Temperature,
)

from homeassistant.components.wolflink.const import (
    COORDINATOR,
    DEVICE_ID,
    DOMAIN,
    MANUFACTURER,
    PARAMETERS,
)
from homeassistant.components.wolflink.sensor import WolfLinkSensor, async_setup_entry
from homeassistant.const import (
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
    sensor = WolfLinkSensor(mock_coordinator, parameter, "mock_device_id", MagicMock())
    mock_coordinator.data = {"outside_temp": [None, 20]}
    assert sensor.native_value == 20


def test_wolflink_sensor_extra_state_attributes(mock_coordinator: MagicMock) -> None:
    """Test WolflinkSensor extra state attributes."""
    parameter = MagicMock()
    parameter.parameter_id = "outside_temp"
    parameter.value_id = "value_id"
    parameter.parent = "parent"
    sensor = WolfLinkSensor(mock_coordinator, parameter, "mock_device_id", MagicMock())
    attributes = sensor.extra_state_attributes
    assert attributes["parameter_id"] == "outside_temp"
    assert attributes["value_id"] == "value_id"
    assert attributes["parent"] == "parent"


@pytest.mark.parametrize(
    ("parameter", "expected_class", "expected_unit"),
    [
        (MagicMock(spec=EnergyParameter), WolfLinkSensor, UnitOfEnergy.KILO_WATT_HOUR),
        (MagicMock(spec=PowerParameter), WolfLinkSensor, UnitOfPower.KILO_WATT),
        (MagicMock(spec=Pressure), WolfLinkSensor, UnitOfPressure.BAR),
        (MagicMock(spec=Temperature), WolfLinkSensor, UnitOfTemperature.CELSIUS),
        (MagicMock(spec=PercentageParameter), WolfLinkSensor, PERCENTAGE),
        (MagicMock(spec=HoursParameter), WolfLinkSensor, UnitOfTime.HOURS),
    ],
)
async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_coordinator: MagicMock,
    parameter: Parameter,
    expected_class: type,
    expected_unit: str,
) -> None:
    """Test async_setup_entry for various parameter types."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=str(CONFIG[DEVICE_ID]), data=CONFIG
    )
    config_entry.add_to_hass(hass)

    parameter.parameter_id = "param_id"
    parameter.name = "Parameter"
    if isinstance(parameter, PercentageParameter):
        parameter.unit = PERCENTAGE
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
    entity = entities[0]
    assert isinstance(entity, expected_class)
    assert entity.native_unit_of_measurement == expected_unit
