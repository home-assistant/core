"""Tests for the sensors provided by the PVOutput integration."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.pvoutput.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("init_integration")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the PVOutput sensors."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_device(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the PVOutput device."""
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "12345"), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry == snapshot

    # The entity snapshots mask the device ID, so check the link explicitly
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert {entity_entry.device_id for entity_entry in entity_entries} == {
        device_entry.id
    }
