"""Test the Wolf SmartSet Service Sensor platform."""

from unittest.mock import MagicMock, Mock

import pytest
from wolf_comm import (
    PERCENTAGE,
    EnergyParameter,
    HoursParameter,
    ListItemParameter,
    Parameter,
    PercentageParameter,
    PowerParameter,
    Pressure,
    SimpleParameter,
    Temperature,
)

from homeassistant.components.wolflink.const import (
    COORDINATOR,
    DEVICE_ID,
    DOMAIN,
    MANUFACTURER,
    PARAMETERS,
)
from homeassistant.components.wolflink.sensor import (
    WolfLinkSensor,
    async_setup_entry,
    get_entity_description,
)
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

from tests.common import Literal, MockConfigEntry


@pytest.fixture
def mock_coordinator(hass: HomeAssistant) -> MagicMock:
    """Mock the Wolf SmartSet Service Coordinator."""
    coordinator = MagicMock()
    coordinator.data = {}
    hass.data[DOMAIN] = {CONFIG[DEVICE_ID]: {COORDINATOR: coordinator}}
    return coordinator


@pytest.fixture
def mock_device_id():
    """Fixture for a mock device ID."""
    return "1234"


@pytest.fixture
def mock_parameter():
    """Fixture for a mock parameter."""
    return Mock(spec=Parameter)


async def mock_config_entry(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test already configured while creating entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=CONFIG[DEVICE_ID], data=CONFIG
    )
    config_entry.add_to_hass(hass)

    device = device_registry.async_get_device({(DOMAIN, CONFIG[DEVICE_ID])})
    assert device is not None
    assert device.identifiers == {(DOMAIN, CONFIG[DEVICE_ID])}


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
        DEVICE_ID: "1234",
    }
    async_add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, async_add_entities)

    assert async_add_entities.call_count == 1
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 1
    entity = entities[0]
    assert isinstance(entity, expected_class)
    assert entity.native_unit_of_measurement == expected_unit


def test_get_entity_description() -> None:
    """Test the get_entity_description function."""
    parameter = Mock(spec=Temperature)
    description = get_entity_description(parameter)
    assert description.device_class == "temperature"
    assert description.native_unit_of_measurement == "°C"

    parameter = Mock(spec=Pressure)
    description = get_entity_description(parameter)
    assert description.device_class == "pressure"
    assert description.native_unit_of_measurement == "bar"

    parameter = Mock(spec=EnergyParameter)
    description = get_entity_description(parameter)
    assert description.device_class == "energy"
    assert description.native_unit_of_measurement == "kWh"

    parameter = Mock(spec=PowerParameter)
    description = get_entity_description(parameter)
    assert description.device_class == "power"
    assert description.native_unit_of_measurement == "kW"

    parameter = Mock(spec=PercentageParameter)
    description = get_entity_description(parameter)
    assert description.native_unit_of_measurement == PERCENTAGE

    parameter = Mock(spec=ListItemParameter)
    description = get_entity_description(parameter)
    assert description.translation_key == "state"

    parameter = Mock(spec=HoursParameter)
    description = get_entity_description(parameter)
    assert description.native_unit_of_measurement == UnitOfTime.HOURS
    assert description.icon == "mdi:clock"

    parameter = Mock(spec=SimpleParameter)
    description = get_entity_description(parameter)


def test_wolflink_sensor(
    mock_coordinator, mock_device_id: Literal["1234"], mock_parameter
) -> None:
    """Test the WolfLinkSensor class."""
    description = get_entity_description(mock_parameter)
    sensor = WolfLinkSensor(
        mock_coordinator, mock_parameter, mock_device_id, description
    )

    assert sensor.entity_description == description
    assert sensor.wolf_object == mock_parameter
    assert sensor._attr_name == description.name
    assert sensor._attr_unique_id == f"{mock_device_id}:{mock_parameter.parameter_id}"
    assert sensor._attr_device_info["identifiers"] == {(DOMAIN, str(mock_device_id))}
    assert (
        sensor._attr_device_info["configuration_url"]
        == "https://www.wolf-smartset.com/"
    )
    assert sensor._attr_device_info["manufacturer"] == MANUFACTURER

    # Test native_value property
    mock_coordinator.data = {mock_parameter.parameter_id: ("value_id", "state")}
    assert sensor.native_value == "state"

    # Test extra_state_attributes property
    assert sensor.extra_state_attributes == {
        "parameter_id": mock_parameter.parameter_id,
        "value_id": mock_parameter.value_id,
        "parent": mock_parameter.parent,
    }
