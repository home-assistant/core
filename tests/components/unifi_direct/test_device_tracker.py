"""Tests for UniFi Direct device tracker."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_device_tracker_entities_created(
    hass: HomeAssistant, mock_config_entry, mock_unifiap
) -> None:
    """Test that device tracker entities are created from coordinator data."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Entity registry should contain the device_tracker entities created by the integration

    registry = er.async_get(hass)
    entries = [
        entry
        for entry in registry.entities.values()
        if entry.domain == "device_tracker" and entry.platform == "unifi_direct"
    ]
    assert len(entries) >= 2

    entity_ids = {entry.entity_id for entry in entries}
    assert "device_tracker.my_phone" in entity_ids
    assert "device_tracker.my_laptop" in entity_ids
