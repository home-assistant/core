"""Tests for the BLUETTI Modbus sensor entities."""

from bluetti_modbus_lib.devices.getter import get_device
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bluetti_modbus.const import (
    DEVICE_TYPE_BALCO260,
    EXCLUDED_FIELDS,
)
from homeassistant.components.bluetti_modbus.sensor import SENSOR_DESCRIPTIONS
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

VOLTAGE_ENTITY = "sensor.balco260_battery_voltage"
ENERGY_ENTITY = "sensor.balco260_total_battery_charged_energy"
BATTERY_LEVEL_ENTITY = "sensor.balco260_battery_soc"
TOTAL_BATTERY_LEVEL_ENTITY = "sensor.balco260_total_battery_soc"
CYCLE_COUNT_ENTITY = "sensor.balco260_battery_cycle_count"

# Shown as DeviceInfo (serial number, firmware) rather than as sensors.
DEVICE_INFO_FIELDS = {"d_serial", "d_ver_arm", "d_ver_dsp"}


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """All sensor entities and their states match the snapshot."""
    await _setup(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_energy_sensor_is_a_total_increasing_counter(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A lifetime energy field gets the energy device class, not a bare number."""
    await _setup(hass, mock_config_entry)

    entry = entity_registry.async_get(ENERGY_ENTITY)
    assert entry is not None

    state = hass.states.get(ENERGY_ENTITY)
    assert state is not None
    assert state.attributes["device_class"] == SensorDeviceClass.ENERGY
    assert state.attributes["state_class"] == SensorStateClass.TOTAL_INCREASING


async def test_only_the_present_charge_level_is_a_battery_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """b_soc gets the battery device class; SoH does not, and b_soc_total is not shown."""
    await _setup(hass, mock_config_entry)

    state = hass.states.get(BATTERY_LEVEL_ENTITY)
    assert state is not None
    assert state.attributes["device_class"] == SensorDeviceClass.BATTERY

    # Reads 0 at the device's own unit id regardless of the real level.
    assert hass.states.get(TOTAL_BATTERY_LEVEL_ENTITY) is None


def test_every_readable_field_has_exactly_one_description() -> None:
    """The static description table and the library's register map stay in step."""
    device = get_device(DEVICE_TYPE_BALCO260)
    assert device is not None
    expected = set(device.field_names()) - EXCLUDED_FIELDS - DEVICE_INFO_FIELDS

    keys = [description.key for description in SENSOR_DESCRIPTIONS]

    assert len(keys) == len(set(keys))
    assert set(keys) == expected


async def test_diagnostic_fields_are_categorized_as_diagnostic(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A count with no physical unit is a diagnostic entity, not a primary one."""
    await _setup(hass, mock_config_entry)

    entry = entity_registry.async_get(CYCLE_COUNT_ENTITY)
    assert entry is not None
    assert entry.entity_category is EntityCategory.DIAGNOSTIC
