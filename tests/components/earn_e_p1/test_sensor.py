"""Tests for the EARN-E P1 Meter sensor platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import trigger_callback

from tests.common import MockConfigEntry, snapshot_platform

# A partial packet carries only the instantaneous values, without energy/gas.
PARTIAL_DEVICE_DATA = {
    "power_delivered": 0.35,
    "power_returned": 0.0,
    "voltage_l1": 232.0,
    "current_l1": 2.0,
}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensor platform with snapshot assertions."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_entity_not_created_when_key_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
) -> None:
    """Test that entities are not created for keys missing from data."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # No entities should exist before first data callback
    state = hass.states.get("sensor.earn_e_p1_meter_power_imported")
    assert state is None

    trigger_callback(mock_listener, device_data={"power_delivered": 1.0})
    await hass.async_block_till_done()

    # power_imported should exist (key power_delivered is in data)
    state = hass.states.get("sensor.earn_e_p1_meter_power_imported")
    assert state is not None
    assert state.state == "1.0"

    # power_exported should NOT exist (key power_returned not in data)
    state = hass.states.get("sensor.earn_e_p1_meter_power_exported")
    assert state is None


async def test_sensors_added_when_key_appears_in_later_packet(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensors are added when their key first appears in a later packet.

    The device emits two packet types: a frequent partial packet with only
    instantaneous values, and a less frequent full packet that also carries
    the energy totals and gas reading. Entities for the full-packet keys must
    be created once that packet arrives, even though the first packet lacked
    them.
    """
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # First packet: only the instantaneous keys are present.
    trigger_callback(mock_listener, device_data=PARTIAL_DEVICE_DATA)
    await hass.async_block_till_done()

    assert len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    ) == len(PARTIAL_DEVICE_DATA)
    assert hass.states.get("sensor.earn_e_p1_meter_energy_imported_tariff_1") is None
    assert hass.states.get("sensor.earn_e_p1_meter_gas_consumed") is None

    # Full packet: energy totals and gas reading now present.
    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 10

    energy = hass.states.get("sensor.earn_e_p1_meter_energy_imported_tariff_1")
    assert energy is not None
    assert energy.state == "12345.678"

    gas = hass.states.get("sensor.earn_e_p1_meter_gas_consumed")
    assert gas is not None
    assert gas.state == "1234.567"


async def test_wifi_rssi_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that Wi-Fi RSSI sensor is disabled by default."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    entry = entity_registry.async_get("sensor.earn_e_p1_meter_wi_fi_rssi")
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
