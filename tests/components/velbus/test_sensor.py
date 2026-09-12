"""Velbus sensor platform tests."""

from unittest.mock import AsyncMock, PropertyMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN,
    Platform,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.velbus.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_vmb8in_counter_energy_unavailable_when_no_energy(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_buttoncounter: AsyncMock,
) -> None:
    """Test VMB8IN-20 counter sensor is unknown when energy has not been received."""
    type(mock_buttoncounter).energy = PropertyMock(return_value=None)
    await init_integration(hass, config_entry)

    state = hass.states.get("sensor.input_buttoncounter_counter")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_vmb7in_gas_counter(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test a VMB7IN gas counter reports a m³ total (regression for #179361)."""
    await init_integration(hass, config_entry)

    total = hass.states.get("sensor.input_gascounter_counter")
    assert total is not None
    assert total.state == "1234.0"
    assert total.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.GAS
    assert total.attributes[ATTR_STATE_CLASS] == SensorStateClass.TOTAL_INCREASING
    assert total.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfVolume.CUBIC_METERS

    flow = hass.states.get("sensor.input_gascounter")
    assert flow is not None
    assert flow.state == "5.0"
    assert flow.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.VOLUME_FLOW_RATE
    assert (
        flow.attributes[ATTR_UNIT_OF_MEASUREMENT]
        == UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR
    )


async def test_vmb7in_water_counter(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test a VMB7IN water counter reports a litre total (regression for #179361)."""
    await init_integration(hass, config_entry)

    total = hass.states.get("sensor.input_watercounter_counter")
    assert total is not None
    assert total.state == "5678.0"
    assert total.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.WATER
    assert total.attributes[ATTR_STATE_CLASS] == SensorStateClass.TOTAL_INCREASING
    assert total.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfVolume.LITERS

    flow = hass.states.get("sensor.input_watercounter")
    assert flow is not None
    assert flow.state == "2.5"
    assert flow.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.VOLUME_FLOW_RATE
    assert (
        flow.attributes[ATTR_UNIT_OF_MEASUREMENT]
        == UnitOfVolumeFlowRate.LITERS_PER_HOUR
    )
