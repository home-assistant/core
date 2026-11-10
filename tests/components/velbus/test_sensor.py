"""Velbus sensor platform tests."""

from unittest.mock import AsyncMock, PropertyMock, patch

from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
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

from . import get_entity_id, init_integration


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
    entity_registry: er.EntityRegistry,
) -> None:
    """Test VMB8IN-20 counter sensor is unknown when energy has not been received."""
    type(mock_buttoncounter).energy = PropertyMock(return_value=None)
    await init_integration(hass, config_entry)

    entity_id = get_entity_id(entity_registry, "sensor", "a1b2c3d4e5f6-2-counter")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_vmb7in_gas_counter(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a VMB7IN gas counter reports a m³ total (regression for #179361)."""
    await init_integration(hass, config_entry)

    total_id = get_entity_id(entity_registry, "sensor", "a1b2c3d4e5f6-5-counter")
    total = hass.states.get(total_id)
    assert total is not None
    assert total.state == "1234.0"
    assert total.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.GAS
    assert total.attributes[ATTR_STATE_CLASS] == SensorStateClass.TOTAL_INCREASING
    assert total.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfVolume.CUBIC_METERS

    flow_id = get_entity_id(entity_registry, "sensor", "a1b2c3d4e5f6-5")
    flow = hass.states.get(flow_id)
    assert flow is not None
    assert flow.state == "5.0"
    assert flow.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.VOLUME_FLOW_RATE
    assert (
        flow.attributes[ATTR_UNIT_OF_MEASUREMENT]
        == UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR
    )


async def test_vmb7in_gas_counter_unavailable_when_no_total(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_gascounter: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the gas total is unknown when no counter total has been received."""
    mock_gascounter.get_counter_total.return_value = None
    await init_integration(hass, config_entry)

    entity_id = get_entity_id(entity_registry, "sensor", "a1b2c3d4e5f6-5-counter")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_vmb7in_water_counter(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a VMB7IN water counter reports a litre total (regression for #179361)."""
    await init_integration(hass, config_entry)

    total_id = get_entity_id(entity_registry, "sensor", "a1b2c3d4e5f6-4-counter")
    total = hass.states.get(total_id)
    assert total is not None
    assert total.state == "5678.0"
    assert total.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.WATER
    assert total.attributes[ATTR_STATE_CLASS] == SensorStateClass.TOTAL_INCREASING
    assert total.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfVolume.LITERS

    flow_id = get_entity_id(entity_registry, "sensor", "a1b2c3d4e5f6-4")
    flow = hass.states.get(flow_id)
    assert flow is not None
    assert flow.state == "2.5"
    assert flow.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.VOLUME_FLOW_RATE
    assert (
        flow.attributes[ATTR_UNIT_OF_MEASUREMENT]
        == UnitOfVolumeFlowRate.LITERS_PER_HOUR
    )


async def test_vmb7in_water_counter_unavailable_when_no_total(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_watercounter: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the water total is unknown when no counter total has been received."""
    mock_watercounter.get_counter_total.return_value = None
    await init_integration(hass, config_entry)

    entity_id = get_entity_id(entity_registry, "sensor", "a1b2c3d4e5f6-4-counter")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN
