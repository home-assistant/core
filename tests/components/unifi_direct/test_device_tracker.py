"""Tests for UniFi AP Direct device tracker."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_registry import EntityRegistry


async def test_device_tracker_entities_created(
    hass: HomeAssistant,
    mock_config_entry,
    mock_unifiap,
    device_registry: dr.DeviceRegistry,
    entity_registry: EntityRegistry,
) -> None:
    """Test that device tracker entities are created from coordinator data."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Entity registry should contain the device_tracker entities created by the integration
    entries = [
        entry
        for entry in entity_registry.entities.values()
        if entry.domain == "device_tracker" and entry.platform == "unifi_direct"
    ]
    assert len(entries) == 2

    entity_ids = {entry.entity_id for entry in entries}
    assert any(
        entity_id.startswith("device_tracker.my_phone") for entity_id in entity_ids
    )
    assert any(
        entity_id.startswith("device_tracker.my_laptop") for entity_id in entity_ids
    )

    assert {entry.original_name for entry in entries} == {None}
    devices = {
        entry.unique_id: device_registry.async_get(entry.device_id) for entry in entries
    }
    assert {mac: device.name for mac, device in devices.items()} == {
        "AA:BB:CC:DD:EE:FF": "my-phone",
        "11:22:33:44:55:66": "my-laptop",
    }
    assert {mac: device.connections for mac, device in devices.items()} == {
        "AA:BB:CC:DD:EE:FF": {(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")},
        "11:22:33:44:55:66": {(dr.CONNECTION_NETWORK_MAC, "11:22:33:44:55:66")},
    }
