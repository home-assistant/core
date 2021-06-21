"""Tests for handling the device registry."""

from homeassistant.components.media_player.const import DOMAIN as MP_DOMAIN
from homeassistant.components.plex.const import DOMAIN


async def test_cleanup_orphaned_devices(hass, entry, setup_plex_server):
    """Test cleaning up orphaned devices on startup."""
    test_device_id = {(DOMAIN, "temporary_device_123")}

    device_registry = await hass.helpers.device_registry.async_get_registry()
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    test_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=test_device_id,
    )
    assert test_device is not None

    test_entity = entity_registry.async_get_or_create(
        MP_DOMAIN, DOMAIN, "entity_unique_id_123", device_id=test_device.id
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
    hass, entry, setup_plex_server, requests_mock, player_plexweb_resources
):
    """Test cleaning up transient devices on startup."""
    plexweb_device_id = {(DOMAIN, "plexweb_id")}
    non_plexweb_device_id = {(DOMAIN, "1234567890123456-com-plexapp-android")}
    plex_client_service_device_id = {(DOMAIN, "plex.tv-clients")}

    device_registry = await hass.helpers.device_registry.async_get_registry()
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    # Pre-create devices and entities to test device migration
    plexweb_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=plexweb_device_id,
        model="Plex Web",
    )
    # plexweb_entity = entity_registry.async_get_or_create(MP_DOMAIN, DOMAIN, "unique_id_123:plexweb_id", suggested_object_id="plex_plex_web_chrome", device_id=plexweb_device.id)
    entity_registry.async_get_or_create(
        MP_DOMAIN,
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
        MP_DOMAIN,
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
        len(
            hass.helpers.entity_registry.async_entries_for_device(
                entity_registry, device_id=plexweb_device.id
            )
        )
        == 1
    )
    assert (
        len(
            hass.helpers.entity_registry.async_entries_for_device(
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
        len(
            hass.helpers.entity_registry.async_entries_for_device(
                entity_registry, device_id=plexweb_device.id
            )
        )
        == 0
    )
    assert (
        len(
            hass.helpers.entity_registry.async_entries_for_device(
                entity_registry, device_id=non_plexweb_device.id
            )
        )
        == 1
    )
    assert (
        len(
            hass.helpers.entity_registry.async_entries_for_device(
                entity_registry, device_id=plex_service_device.id
            )
        )
        == 1
    )
