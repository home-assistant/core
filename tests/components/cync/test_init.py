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
    """Test migration to mesh-based entity and device registry IDs."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, version=1)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={
            (DOMAIN, "1000-1101"),
            (DOMAIN, "1000-1112"),
            ("another_domain", "external-id"),
        },
    )
    light_entry = entity_registry.async_get_or_create(
        Platform.LIGHT,
        DOMAIN,
        "1000-1101",
        config_entry=mock_config_entry,
        device_id=device_entry.id,
    )
    offline_light_entry = entity_registry.async_get_or_create(
        Platform.LIGHT,
        DOMAIN,
        "1000-1112",
        config_entry=mock_config_entry,
        device_id=device_entry.id,
    )
    switch_device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "1000-1006")},
    )
    switch_entry = entity_registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        "1000-1101",
        config_entry=mock_config_entry,
        device_id=switch_device_entry.id,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.version == 2
    migrated_light = entity_registry.async_get(light_entry.entity_id)
    assert migrated_light is not None
    assert migrated_light.unique_id == "1000-1"
    migrated_device = device_registry.async_get(device_entry.id)
    assert migrated_device is not None
    assert (DOMAIN, "1000-1") in migrated_device.identifiers
    assert (DOMAIN, "1000-3") in migrated_device.identifiers
    assert (DOMAIN, "1000-1101") not in migrated_device.identifiers
    assert (DOMAIN, "1000-1112") not in migrated_device.identifiers
    assert ("another_domain", "external-id") in migrated_device.identifiers

    migrated_offline_light = entity_registry.async_get(offline_light_entry.entity_id)
    assert migrated_offline_light is not None
    assert migrated_offline_light.unique_id == "1000-3"
    migrated_offline_device = device_registry.async_get(device_entry.id)
    assert migrated_offline_device is not None
    assert (DOMAIN, "1000-3") in migrated_offline_device.identifiers
    assert (DOMAIN, "1000-1112") not in migrated_offline_device.identifiers

    current_switch = entity_registry.async_get(switch_entry.entity_id)
    assert current_switch is not None
    assert current_switch.unique_id == "1000-1101"
    current_switch_device = device_registry.async_get(switch_device_entry.id)
    assert current_switch_device is not None
    assert (DOMAIN, "1000-1006") in current_switch_device.identifiers

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(light_entry.entity_id) == migrated_light
    reloaded_device = device_registry.async_get(device_entry.id)
    assert reloaded_device is not None
    assert reloaded_device.identifiers == migrated_device.identifiers
