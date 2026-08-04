"""The Jellyfin integration."""

from collections.abc import Callable
from typing import Any

from homeassistant.const import CONF_URL
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import (
    EVENT_DEVICE_REGISTRY_UPDATED,
    EventDeviceRegistryUpdatedData,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .client_wrapper import CannotConnect, InvalidAuth, create_client, validate_input
from .const import CONF_CLIENT_DEVICE_ID, DEFAULT_NAME, DOMAIN, LOGGER, PLATFORMS
from .coordinator import JellyfinConfigEntry, JellyfinDataUpdateCoordinator
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Jellyfin component."""
    await async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: JellyfinConfigEntry) -> bool:
    """Set up Jellyfin from a config entry."""
    if CONF_CLIENT_DEVICE_ID not in entry.data:
        entry_data = entry.data.copy()
        entry_data[CONF_CLIENT_DEVICE_ID] = entry.entry_id
        hass.config_entries.async_update_entry(entry, data=entry_data)

    device_id = entry.data[CONF_CLIENT_DEVICE_ID]
    device_name = ascii(hass.config.location_name)

    client = create_client(device_id=device_id, device_name=device_name)

    try:
        user_id, connect_result = await validate_input(hass, dict(entry.data), client)
    except CannotConnect as ex:
        raise ConfigEntryNotReady("Cannot connect to Jellyfin server") from ex
    except InvalidAuth as ex:
        raise ConfigEntryAuthFailed(ex) from ex

    server_info: dict[str, Any] = connect_result["Servers"][0]

    coordinator = JellyfinDataUpdateCoordinator(
        hass, entry, client, server_info, user_id
    )
    await coordinator.async_config_entry_first_refresh()

    # Migrate config entry unique_id from bare user_id to {server_id}-{user_id}.
    expected_unique_id = f"{coordinator.server_id}-{coordinator.user_id}"
    if entry.unique_id != expected_unique_id:
        hass.config_entries.async_update_entry(entry, unique_id=expected_unique_id)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        entry_type=dr.DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, coordinator.server_id)},
        manufacturer=DEFAULT_NAME,
        name=coordinator.server_name,
        sw_version=coordinator.server_version,
    )

    _migrate_device_identifiers(
        hass,
        entry,
        coordinator.server_id,
        coordinator.user_id,
        set(coordinator.known_devices) | set(coordinator.data),
    )
    # Migrate entity unique IDs before forwarding platform setups to prevent
    # the remote platform from registering a new device-based unique ID before
    # media_player can migrate the old session-based one, causing a collision.
    _migrate_unique_ids(hass, coordinator)

    entry.runtime_data = coordinator
    entry.async_on_unload(client.stop)
    entry.async_on_unload(
        hass.bus.async_listen(
            EVENT_DEVICE_REGISTRY_UPDATED,
            _handle_device_removed(coordinator),
            event_filter=_device_removed_filter,
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: JellyfinConfigEntry) -> bool:
    """Migrate an old config entry."""
    if entry.version == 1 and entry.minor_version < 2:
        new_data = {**entry.data, CONF_URL: entry.data[CONF_URL].rstrip("/")}
        hass.config_entries.async_update_entry(entry, data=new_data, minor_version=2)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: JellyfinConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: JellyfinConfigEntry) -> None:
    """Remove a config entry and clean up stored data."""
    store: Store[dict[str, Any]] = Store(hass, 1, f"jellyfin_{entry.entry_id}_devices")
    await store.async_remove()


def _migrate_device_identifiers(
    hass: HomeAssistant,
    entry: JellyfinConfigEntry,
    server_id: str,
    user_id: str,
    known_device_ids: set[str],
) -> None:
    """Migrate bare client device identifiers to the fully-scoped format.

    Before this integration tracked devices persistently, client devices were
    registered as (DOMAIN, device_id) with no server or user scoping. These
    are updated in place to (DOMAIN, {server_id}-{user_id}-{device_id}),
    preserving area assignments and name overrides.

    Only identifiers matching a known Jellyfin device ID for this entry are
    migrated, preventing double-prefixing when multiple config entries share a
    device registry entry.
    """
    device_registry = dr.async_get(hass)
    full_prefix = f"{server_id}-{user_id}-"
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        for domain, identifier in device_entry.identifiers:
            if domain != DOMAIN:
                continue
            if identifier == server_id or identifier.startswith(full_prefix):
                # Server device or already fully scoped — nothing to do.
                break
            if identifier not in known_device_ids:
                # Not a bare device ID belonging to this entry — skip.
                break
            new_identifiers = (device_entry.identifiers - {(DOMAIN, identifier)}) | {
                (DOMAIN, f"{server_id}-{user_id}-{identifier}")
            }
            device_registry.async_update_device(
                device_entry.id,
                new_identifiers=new_identifiers,
            )
            break


@callback
def _device_removed_filter(event_data: EventDeviceRegistryUpdatedData) -> bool:
    """Filter device registry events to only removals."""
    return event_data["action"] == "remove"


def _handle_device_removed(
    coordinator: JellyfinDataUpdateCoordinator,
) -> Callable[[Event[EventDeviceRegistryUpdatedData]], None]:
    """Return a handler that purges a removed Jellyfin client device from storage."""

    @callback
    def handle(event: Event[EventDeviceRegistryUpdatedData]) -> None:
        # The event filter guarantees action == "remove". The remove payload
        # includes a "device" snapshot with the identifiers of the deleted device.
        # We narrow the type explicitly so mypy accepts the "device" key access.
        if event.data["action"] != "remove":
            return
        device: dict[str, Any] = event.data["device"]
        prefix = f"{coordinator.server_id}-{coordinator.user_id}-"
        for domain, identifier in device.get("identifiers", []):
            if domain != DOMAIN or not identifier.startswith(prefix):
                continue
            jellyfin_device_id = identifier[len(prefix) :]
            if jellyfin_device_id not in coordinator.known_devices:
                continue
            coordinator.known_devices.pop(jellyfin_device_id)
            coordinator.session_device_map = {
                sid: did
                for sid, did in coordinator.session_device_map.items()
                if did != jellyfin_device_id
            }
            coordinator.device_player_ids.discard(jellyfin_device_id)
            coordinator.device_remote_ids.discard(jellyfin_device_id)
            coordinator.hass.async_create_task(coordinator.async_persist())
            break

    return handle


def _migrate_unique_ids(
    hass: HomeAssistant, coordinator: JellyfinDataUpdateCoordinator
) -> None:
    """Migrate entity unique IDs from the session-based to device-based format.

    The original integration used {server_id}-{session_id} as the unique ID.
    Session IDs are transient, so these are migrated to the stable format
    {server_id}-{user_id}-{device_id} using session_device_map to resolve
    the device_id for any offline devices.
    """
    registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    session_to_device = {
        **coordinator.session_device_map,
        **{session["Id"]: device_id for device_id, session in coordinator.data.items()},
    }
    prefix = f"{coordinator.server_id}-"
    full_prefix = f"{coordinator.server_id}-{coordinator.user_id}-"
    for entity_entry in er.async_entries_for_config_entry(
        registry, coordinator.config_entry.entry_id
    ):
        uid = entity_entry.unique_id
        if not uid.startswith(prefix) or uid.startswith(full_prefix):
            continue
        suffix = uid[len(prefix) :]
        device_id = session_to_device.get(suffix)
        if device_id is None and entity_entry.device_id:
            # No session map entry — fall back to device registry for devices
            # that were offline on first upgrade (store not yet populated).
            dev = device_registry.async_get(entity_entry.device_id)
            if dev:
                for dom, ident in dev.identifiers:
                    if dom == DOMAIN and ident.startswith(full_prefix):
                        device_id = ident[len(full_prefix) :]
                        break
        if device_id is None:
            continue
        new_unique_id = f"{coordinator.server_id}-{coordinator.user_id}-{device_id}"
        LOGGER.debug(
            "Migrating entity %s unique_id from %s to %s",
            entity_entry.entity_id,
            uid,
            new_unique_id,
        )
        registry.async_update_entity(
            entity_entry.entity_id, new_unique_id=new_unique_id
        )


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: JellyfinConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove device from a config entry."""
    coordinator = config_entry.runtime_data

    return not device_entry.identifiers.intersection(
        {
            (DOMAIN, coordinator.server_id),
            *(
                (DOMAIN, f"{coordinator.server_id}-{coordinator.user_id}-{device_id}")
                for device_id in coordinator.data
            ),
        }
    )
