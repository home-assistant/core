"""Tests for handling the device registry."""
import requests_mock

from homeassistant.components.plex.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


async def test_cleanup_orphaned_devices(
    hass: HomeAssistant, entry, setup_plex_server
) -> None:
    """Test cleaning up orphaned devices on startup."""
    test_device_id = {(DOMAIN, "temporary_device_123")}

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    entry.add_to_hass(hass)

    test_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=test_device_id,
    )
    assert test_device is not None

    test_entity = entity_registry.async_get_or_create(
        Platform.MEDIA_PLAYER, DOMAIN, "entity_unique_id_123", device_id=test_device.id
    )
    assert test_entity is not None

    # Ensure device is not removed with an entity
    await setup_plex_server()
    device = device_registry.async_get_device(identifiers=test_device_id)
    assert device is not None

    await hass.config_entries.async_unload(entry.entry_id)

    # Ensure device is removed without an entity
    entity_registry.async_remove(test_entity.entity_id)
    await setup_plex_server()
    device = device_registry.async_get_device(identifiers=test_device_id)
    assert device is None


async def test_migrate_transient_devices(
    hass: HomeAssistant,
    entry,
    setup_plex_server,
    requests_mock: requests_mock.Mocker,
    player_plexweb_resources,
) -> None:
    """Test cleaning up transient devices on startup."""
    plexweb_device_id = {(DOMAIN, "plexweb_id")}
    non_plexweb_device_id = {(DOMAIN, "1234567890123456-com-plexapp-android")}
    plex_client_service_device_id = {(DOMAIN, "plex.tv-clients")}

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    entry.add_to_hass(hass)

    # Pre-create devices and entities to test device migration
    plexweb_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=plexweb_device_id,
        model="Plex Web",
    )

    entity_registry.async_get_or_create(
        Platform.MEDIA_PLAYER,
        DOMAIN,
        "unique_id_123:plexweb_id",
        suggested_object_id="plex_plex_web_chrome",
        device_id=plexweb_device.id,
    )

    non_plexweb_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=non_plexweb_device_id,
        model="Plex for Android (TV)",
    )
    entity_registry.async_get_or_create(
        Platform.MEDIA_PLAYER,
        DOMAIN,
        "unique_id_123:1234567890123456-com-plexapp-android",
        suggested_object_id="plex_plex_for_android_tv_shield_android_tv",
        device_id=non_plexweb_device.id,
    )

    # Ensure the Plex Web client is available
    requests_mock.get("/resources", text=player_plexweb_resources)

    plexweb_device = device_registry.async_get_device(identifiers=plexweb_device_id)
    non_plexweb_device = device_registry.async_get_device(
        identifiers=non_plexweb_device_id
    )
    plex_service_device = device_registry.async_get_device(
        identifiers=plex_client_service_device_id
    )

    assert (
        len(er.async_entries_for_device(entity_registry, device_id=plexweb_device.id))
        == 1
    )
    assert (
        len(
            er.async_entries_for_device(
                entity_registry, device_id=non_plexweb_device.id
            )
        )
        == 1
    )
    assert plex_service_device is None

    # Ensure Plex Web entity is migrated to a service
    await setup_plex_server()

    plex_service_device = device_registry.async_get_device(
        identifiers=plex_client_service_device_id
    )

    assert (
        len(er.async_entries_for_device(entity_registry, device_id=plexweb_device.id))
        == 0
    )
    assert (
        len(
            er.async_entries_for_device(
                entity_registry, device_id=non_plexweb_device.id
            )
        )
        == 1
    )
    assert (
        len(
            er.async_entries_for_device(
                entity_registry, device_id=plex_service_device.id
            )
        )
        == 1
    )
