"""Tests for the Cync integration setup."""

from homeassistant.components.cync.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_migrate_unique_ids(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that entity and device registry IDs are migrated from device_id to mesh_device_id format."""
    mock_config_entry.add_to_hass(hass)

    old_device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "10000-1101"), ("another_domain", "external-id")},
    )
    old_light_entry = entity_registry.async_get_or_create(
        Platform.LIGHT,
        "cync",
        "10000-1101",
        config_entry=mock_config_entry,
    )
    original_entity_id = old_light_entry.entity_id
    original_device_id = old_device_entry.id
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    migrated_entity = entity_registry.async_get(original_entity_id)
    assert migrated_entity is not None
    assert migrated_entity.entity_id == original_entity_id
    assert migrated_entity.unique_id == "10000-1"
    migrated_device = device_registry.async_get(old_device_entry.id)
    assert migrated_device is not None
    assert migrated_device.id == original_device_id
    assert (DOMAIN, "10000-1") in migrated_device.identifiers
    assert (DOMAIN, "10000-1101") not in migrated_device.identifiers
    assert ("another_domain", "external-id") in migrated_device.identifiers

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(original_entity_id) == migrated_entity
    assert device_registry.async_get(original_device_id) == migrated_device
