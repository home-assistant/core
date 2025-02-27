"""Test the Wolf SmartSet Service Sensor platform."""

from unittest.mock import MagicMock, Mock

import pytest
from syrupy import SnapshotAssertion
from wolf_comm import (
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
    PARAMETERS,
)
from homeassistant.components.wolflink.sensor import WolfLinkSensor, async_setup_entry
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
def mock_device_id() -> str:
    """Fixture for a mock device ID."""
    return "1234"


@pytest.fixture
def mock_parameter() -> Parameter:
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


def test_wolflink_sensor_native_value() -> None:
    """Test WolflinkSensor native value."""
    coordinator = MagicMock()
    parameter = MagicMock()
    parameter.parameter_id = "outside_temp"
    sensor = WolfLinkSensor(coordinator, parameter, "mock_device_id", MagicMock())
    coordinator.data = {"outside_temp": [None, 20]}
    assert sensor.native_value == 20


def test_wolflink_sensor_extra_state_attributes() -> None:
    """Test WolflinkSensor extra state attributes."""
    coordinator = MagicMock()
    parameter = MagicMock()
    parameter.parameter_id = "outside_temp"
    parameter.value_id = "value_id"
    parameter.parent = "parent"
    sensor = WolfLinkSensor(coordinator, parameter, "mock_device_id", MagicMock())
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
    parameter: Parameter,
    wolf_parameter: Parameter,
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
        DEVICE_ID: "1234",
        COORDINATOR: MagicMock(),  # Ensure COORDINATOR is set up
    }
    async_add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, async_add_entities)

    assert async_add_entities.call_count == 1
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 1
    entity = entities[0]
    assert isinstance(entity, expected_class)
    assert entity.native_unit_of_measurement == expected_unit


@pytest.fixture(
    params=[
        EnergyParameter(6002800000, "Energy Parameter", "Heating", 6005200000),
        ListItemParameter(
            8002800000,
            "List Item Parameter",
            "Heating",
            (["Pump", "on"], ["Heating", "on"]),
            8005200000,
        ),
        PowerParameter(5002800000, "Power Parameter", "Heating", 5005200000),
        Pressure(4002800000, "Pressure Parameter", "Heating", 4005200000),
        Temperature(3002800000, "Temperature Parameter", "Solar", 3005200000),
        PercentageParameter(2002800000, "Percentage Parameter", "Solar", 2005200000),
        HoursParameter(7002800000, "Hours Parameter", "Heating", 7005200000),
        SimpleParameter(1002800000, "Simple Parameter", "DHW", 1005200000),
    ]
)
def wolf_parameter(request: pytest.FixtureRequest) -> Parameter:
    """Fixture for different WolfLink parameter types."""
    return request.param


async def test_sensor(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    wolf_parameter: Parameter,
) -> None:
    """Test the sensor state for various parameter types."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=str(CONFIG[DEVICE_ID]), data=CONFIG
    )
    config_entry.add_to_hass(hass)

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        PARAMETERS: [wolf_parameter],
        DEVICE_ID: "1234",
        COORDINATOR: MagicMock(),  # Ensure COORDINATOR is set up
    }
    async_add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, async_add_entities)

    state = hass.states.get(f"{wolf_parameter.parameter_id}")
    assert state == snapshot
