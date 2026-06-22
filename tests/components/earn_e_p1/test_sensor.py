"""Tests for the EARN-E P1 Meter sensor platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import trigger_callback

from tests.common import MockConfigEntry, snapshot_platform


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
