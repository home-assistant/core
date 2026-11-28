"""Tests for handling the device registry."""

from collections.abc import Awaitable, Callable

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import WebSocketGenerator
import requests_mock

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, ButtonService
from homeassistant.components.plex.const import DOMAIN
from homeassistant.components.plex.server import PlexServer
from homeassistant.const import STATE_UNAVAILABLE, Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .helpers import wait_for_debouncer

CLIENT_ID = "1234567890123456-com-plexapp-android"
CLIENT_ENTITY_ID = "media_player.plex_plex_for_android_tv_shield_android_tv"


async def _scan_clients(hass: HomeAssistant) -> None:
    """Press the scan clients button once the update debouncer has cooled down."""
    await wait_for_debouncer(hass)
    await hass.services.async_call(
        BUTTON_DOMAIN,
        ButtonService.PRESS,
        {TargetKey.ENTITY_ID: "button.plex_server_1_scan_clients"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_cleanup_orphaned_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    entry,
    setup_plex_server,
) -> None:
    """Test cleaning up orphaned devices on startup."""
    test_device_id = {(DOMAIN, "temporary_device_123")}

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
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "temporary_device_123"), entry.entry_id
    )
    assert device is not None

    await hass.config_entries.async_unload(entry.entry_id)

    # Ensure device is removed without an entity
    entity_registry.async_remove(test_entity.entity_id)
    await setup_plex_server()
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "temporary_device_123"), entry.entry_id
    )
    assert device is None


async def test_migrate_transient_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    entry,
    setup_plex_server,
    requests_mock: requests_mock.Mocker,
    player_plexweb_resources,
) -> None:
    """Test cleaning up transient devices on startup."""
    plexweb_device_id = {(DOMAIN, "plexweb_id")}
    non_plexweb_device_id = {(DOMAIN, "1234567890123456-com-plexapp-android")}

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

    plexweb_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "plexweb_id"), entry.entry_id
    )
    non_plexweb_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "1234567890123456-com-plexapp-android"), entry.entry_id
    )
    plex_service_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "plex.tv-clients"), entry.entry_id
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

    plex_service_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "plex.tv-clients"), entry.entry_id
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


async def test_remove_config_entry_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
    setup_plex_server: Callable[..., Awaitable[PlexServer]],
    requests_mock: requests_mock.Mocker,
    empty_payload: str,
    session_default: str,
) -> None:
    """Test only client devices that are no longer available can be removed."""
    assert await async_setup_component(hass, "config", {})
    mock_plex_server = await setup_plex_server()
    client = await hass_ws_client(hass)

    server_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.unique_id), entry.entry_id
    )
    response = await client.remove_device(server_device.id)
    assert not response["success"]

    client_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, CLIENT_ID), entry.entry_id
    )
    response = await client.remove_device(client_device.id)
    assert not response["success"]

    url = mock_plex_server.url_in_use
    requests_mock.get(f"{url}/clients", text=empty_payload)
    requests_mock.get(f"{url}/status/sessions", text=empty_payload)
    await _scan_clients(hass)
    assert hass.states.get(CLIENT_ENTITY_ID).state == STATE_UNAVAILABLE

    response = await client.remove_device(client_device.id)
    assert response["success"]
    await hass.async_block_till_done()
    assert device_registry.async_get(client_device.id) is None
    assert entity_registry.async_get(CLIENT_ENTITY_ID) is None
    assert hass.states.get(CLIENT_ENTITY_ID) is None

    # A forgotten client gets a new device and entity when it returns
    requests_mock.get(f"{url}/status/sessions", text=session_default)
    await _scan_clients(hass)
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, CLIENT_ID), entry.entry_id
    )
    assert hass.states.get(CLIENT_ENTITY_ID).state != STATE_UNAVAILABLE


async def test_remove_stale_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
    setup_plex_server: Callable[..., Awaitable[PlexServer]],
) -> None:
    """Test removing a client device that has not been seen since startup."""
    assert await async_setup_component(hass, "config", {})
    entry.add_to_hass(hass)
    stale_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "stale_client")},
    )
    stale_entity = entity_registry.async_get_or_create(
        Platform.MEDIA_PLAYER,
        DOMAIN,
        f"{entry.unique_id}:stale_client",
        config_entry=entry,
        device_id=stale_device.id,
    )
    await setup_plex_server()
    client = await hass_ws_client(hass)

    response = await client.remove_device(stale_device.id)
    assert response["success"]
    await hass.async_block_till_done()
    assert device_registry.async_get(stale_device.id) is None
    assert entity_registry.async_get(stale_entity.entity_id) is None
