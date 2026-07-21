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

    # Pre-populate registries with old-format identifiers (home_id-device_id)
    old_device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "1000-1101")},
    )
    old_light_entry = entity_registry.async_get_or_create(
        Platform.LIGHT,
        "cync",
        "1000-1101",
        config_entry=mock_config_entry,
    )
    old_switch_entry = entity_registry.async_get_or_create(
        Platform.SWITCH,
        "cync",
        "1000-1201",
        config_entry=mock_config_entry,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Entity unique IDs should use the new mesh_device_id format
    assert entity_registry.async_get(old_light_entry.entity_id).unique_id == "1000-1"
    assert entity_registry.async_get(old_switch_entry.entity_id).unique_id == "1000-4"

    # Device registry identifier should also be updated
    migrated_device = device_registry.async_get(old_device_entry.id)
    assert (DOMAIN, "1000-1") in migrated_device.identifiers
