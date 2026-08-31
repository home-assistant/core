"""Tests for the Cync integration setup."""

from unittest.mock import MagicMock, patch

from pycync import CyncLight
from pycync.exceptions import CyncError

from homeassistant.components.cync.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

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
        identifiers={(DOMAIN, "1000-1111")},
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
    assert "mesh_unique_ids_migration_pending" not in mock_config_entry.data
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
    assert (DOMAIN, "1000-1111") in current_switch_device.identifiers

    colliding_mesh_entry = entity_registry.async_get_or_create(
        Platform.LIGHT,
        DOMAIN,
        "1000-1101",
        config_entry=mock_config_entry,
    )

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert entity_registry.async_get(light_entry.entity_id) == migrated_light
    reloaded_device = device_registry.async_get(device_entry.id)
    assert reloaded_device is not None
    assert reloaded_device.identifiers == migrated_device.identifiers
    assert (
        entity_registry.async_get(colliding_mesh_entry.entity_id)
        == colliding_mesh_entry
    )


async def test_migrate_device_without_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test migration preserves a device whose entity was removed."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, version=1)
    area_entry = area_registry.async_get_or_create("Porch")
    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "1000-1112")},
        name="Offline light",
    )
    device_registry.async_update_device(
        device_entry.id,
        area_id=area_entry.id,
        labels={"outside"},
        name_by_user="Porch light",
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    migrated_device = device_registry.async_get(device_entry.id)
    assert migrated_device is not None
    assert migrated_device.identifiers == {(DOMAIN, "1000-3")}
    assert migrated_device.area_id == area_entry.id
    assert migrated_device.labels == {"outside"}
    assert migrated_device.name_by_user == "Porch light"


async def test_resume_entityless_device_finalization(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    cync_client: MagicMock,
) -> None:
    """Test retry does not remap an already-final entity-less identifier."""
    home = cync_client.get_homes()[0]
    lights = [
        device
        for device in home.get_flattened_device_list()
        if isinstance(device, CyncLight)
    ]
    next(light for light in lights if light.device_id == 1111).mesh_device_id = 1101

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            "mesh_unique_ids_migration_pending": True,
        },
    )
    chained_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "1000-1111")},
    )
    first_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "1000-1101")},
    )

    original_update_device = device_registry.async_update_device
    failed = False

    def fail_after_chained_device_finalization(
        device_id: str, *, new_identifiers: set[tuple[str, str]]
    ) -> dr.DeviceEntry | None:
        nonlocal failed
        result = original_update_device(device_id, new_identifiers=new_identifiers)
        if not failed and new_identifiers == {(DOMAIN, "1000-1101")}:
            failed = True
            raise RuntimeError
        return result

    with patch.object(
        device_registry,
        "async_update_device",
        side_effect=fail_after_chained_device_finalization,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.data["mesh_unique_ids_device_finalize_pending"] is True

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    migrated_chained_device = device_registry.async_get(chained_device.id)
    assert migrated_chained_device is not None
    assert migrated_chained_device.identifiers == {(DOMAIN, "1000-1101")}
    migrated_first_device = device_registry.async_get(first_device.id)
    assert migrated_first_device is not None
    assert migrated_first_device.identifiers == {(DOMAIN, "1000-1")}
    assert "mesh_unique_ids_migration_pending" not in mock_config_entry.data
    assert "mesh_unique_ids_device_finalize_pending" not in mock_config_entry.data


async def test_migration_without_lights_clears_marker(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    cync_client: MagicMock,
) -> None:
    """Test an empty migration still clears its pending marker."""
    cync_client.get_homes.return_value = []
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            "mesh_unique_ids_migration_pending": True,
        },
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert "mesh_unique_ids_migration_pending" not in mock_config_entry.data


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
        identifiers={(DOMAIN, "1000-1101")},
    )
    partially_migrated_entity = entity_registry.async_get_or_create(
        Platform.LIGHT,
        DOMAIN,
        "1000-1111",
        config_entry=mock_config_entry,
        device_id=device_entry.id,
    )
    entity_registry.async_update_entity(
        partially_migrated_entity.entity_id,
        new_unique_id="1000-1",
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    migrated_device = device_registry.async_get(device_entry.id)
    assert migrated_device is not None
    assert (DOMAIN, "1000-1") in migrated_device.identifiers
    assert (DOMAIN, "1000-1101") not in migrated_device.identifiers
    assert "mesh_unique_ids_migration_pending" not in mock_config_entry.data


async def test_migrate_overlapping_unique_ids(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    cync_client: MagicMock,
) -> None:
    """Test direct migration orders overlapping IDs safely."""
    home = cync_client.get_homes()[0]
    lights = [
        device
        for device in home.get_flattened_device_list()
        if isinstance(device, CyncLight)
    ]
    next(light for light in lights if light.device_id == 1111).mesh_device_id = 1101

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            "mesh_unique_ids_migration_pending": True,
        },
    )
    merged_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "1000-1111"), (DOMAIN, "1000-1101")},
    )
    chained_entity = entity_registry.async_get_or_create(
        Platform.LIGHT,
        DOMAIN,
        "1000-1111",
        config_entry=mock_config_entry,
        device_id=merged_device.id,
    )
    first_entity = entity_registry.async_get_or_create(
        Platform.LIGHT,
        DOMAIN,
        "1000-1101",
        config_entry=mock_config_entry,
        device_id=merged_device.id,
    )

    original_update_device = device_registry.async_update_device
    update_count = 0

    def fail_second_device_update(
        device_id: str, *, new_identifiers: set[tuple[str, str]]
    ) -> dr.DeviceEntry | None:
        nonlocal update_count
        update_count += 1
        if update_count == 2:
            raise RuntimeError
        return original_update_device(device_id, new_identifiers=new_identifiers)

    with patch.object(
        device_registry,
        "async_update_device",
        side_effect=fail_second_device_update,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.data["mesh_unique_ids_migration_pending"] is True

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    current_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert current_entry is not None
    assert current_entry.state is ConfigEntryState.LOADED
    migrated_chained_entity = entity_registry.async_get(chained_entity.entity_id)
    assert migrated_chained_entity is not None
    assert migrated_chained_entity.unique_id == "1000-1101"
    assert migrated_chained_entity.previous_unique_id == "1000-1111"
    migrated_first_entity = entity_registry.async_get(first_entity.entity_id)
    assert migrated_first_entity is not None
    assert migrated_first_entity.unique_id == "1000-1"
    assert migrated_first_entity.previous_unique_id == "1000-1101"
    migrated_device = device_registry.async_get(merged_device.id)
    assert migrated_device is not None
    assert migrated_device.identifiers == {
        (DOMAIN, "1000-1101"),
        (DOMAIN, "1000-1"),
    }
    assert "mesh_unique_ids_migration_pending" not in mock_config_entry.data


async def test_migration_failure_closes_client_and_keeps_marker(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    cync_client: MagicMock,
) -> None:
    """Test a failed registry update is retried and closes the client."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            "mesh_unique_ids_migration_pending": True,
        },
    )
    light_entry = entity_registry.async_get_or_create(
        Platform.LIGHT,
        DOMAIN,
        "1000-1101",
        config_entry=mock_config_entry,
    )

    with patch.object(entity_registry, "async_update_entity", side_effect=RuntimeError):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    cync_client.shut_down.assert_awaited_once()
    assert mock_config_entry.data["mesh_unique_ids_migration_pending"] is True
    interrupted_light = entity_registry.async_get(light_entry.entity_id)
    assert interrupted_light is not None
    assert interrupted_light.unique_id == "1000-1101"

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    current_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert current_entry is not None
    assert current_entry.state is ConfigEntryState.LOADED
    migrated_light = entity_registry.async_get(light_entry.entity_id)
    assert migrated_light is not None
    assert migrated_light.unique_id == "1000-1"
    assert "mesh_unique_ids_migration_pending" not in mock_config_entry.data
