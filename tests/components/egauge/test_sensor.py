"""Tests for the eGauge sensor platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.egauge.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Verify device created with hostname
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "ABC123456")})
    assert device_entry
    assert device_entry.name == "egauge-home"
    assert device_entry.serial_number == "ABC123456"
    assert device_entry.manufacturer == "eGauge Systems"
    assert device_entry.model == "eGauge Energy Monitor"

    # Verify all entities assigned to device
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id

    # Verify only power sensors created (4 total: 2 power + 2 energy)
    # Temperature register should be gracefully ignored
    assert len(entity_entries) == 4
