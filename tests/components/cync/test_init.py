"""Tests for the Cync integration setup."""

from unittest.mock import patch

from pycync.exceptions import CyncError

from homeassistant.components.cync.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_migrate_entry_does_not_connect(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test config entry migration does not require cloud access."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, version=1)

    with patch("homeassistant.components.cync.Cync.create", side_effect=CyncError):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.version == 2
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.data["mesh_unique_ids_migration_pending"] is True


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
            (DOMAIN, "10000-1101"),
            (DOMAIN, "10000-1112"),
            ("another_domain", "external-id"),
        },
    )
    light_entry = entity_registry.async_get_or_create(
        Platform.LIGHT,
        DOMAIN,
        "10000-1101",
        config_entry=mock_config_entry,
        device_id=device_entry.id,
    )
    offline_light_entry = entity_registry.async_get_or_create(
        Platform.LIGHT,
        DOMAIN,
        "10000-1112",
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
        "10000-1101",
        config_entry=mock_config_entry,
        device_id=switch_device_entry.id,
    )
    original_entity_id = light_entry.entity_id
    original_device_id = device_entry.id
    offline_entity_id = offline_light_entry.entity_id

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.version == 2
    assert "mesh_unique_ids_migration_pending" not in mock_config_entry.data
    migrated_entity = entity_registry.async_get(original_entity_id)
    assert migrated_entity is not None
    assert migrated_entity.entity_id == original_entity_id
    assert migrated_entity.unique_id == "10000-1"
    migrated_device = device_registry.async_get(original_device_id)
    assert migrated_device is not None
    assert migrated_device.id == original_device_id
    assert (DOMAIN, "10000-1") in migrated_device.identifiers
    assert (DOMAIN, "10000-3") in migrated_device.identifiers
    assert (DOMAIN, "10000-1101") not in migrated_device.identifiers
    assert (DOMAIN, "10000-1112") not in migrated_device.identifiers
    assert ("another_domain", "external-id") in migrated_device.identifiers

    migrated_offline_entity = entity_registry.async_get(offline_entity_id)
    assert migrated_offline_entity is not None
    assert migrated_offline_entity.unique_id == "10000-3"

    current_switch = entity_registry.async_get(switch_entry.entity_id)
    assert current_switch is not None
    assert current_switch.unique_id == "10000-1101"
    current_switch_device = device_registry.async_get(switch_device_entry.id)
    assert current_switch_device is not None
    assert (DOMAIN, "1000-1006") in current_switch_device.identifiers

    colliding_mesh_entry = entity_registry.async_get_or_create(
        Platform.LIGHT,
        DOMAIN,
        "10000-1101",
        config_entry=mock_config_entry,
    )

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert entity_registry.async_get(original_entity_id) == migrated_entity
    reloaded_device = device_registry.async_get(original_device_id)
    assert reloaded_device is not None
    assert reloaded_device.identifiers == migrated_device.identifiers
    assert (
        entity_registry.async_get(colliding_mesh_entry.entity_id)
        == colliding_mesh_entry
    )


async def test_resume_partial_unique_id_migration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test retry migrates a device after its entity was already migrated."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            "mesh_unique_ids_migration_pending": True,
        },
    )
    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "10000-1101")},
    )
    entity_registry.async_get_or_create(
        Platform.LIGHT,
        DOMAIN,
        "10000-1",
        config_entry=mock_config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    migrated_device = device_registry.async_get(device_entry.id)
    assert migrated_device is not None
    assert (DOMAIN, "10000-1") in migrated_device.identifiers
    assert (DOMAIN, "10000-1101") not in migrated_device.identifiers
    assert "mesh_unique_ids_migration_pending" not in mock_config_entry.data
