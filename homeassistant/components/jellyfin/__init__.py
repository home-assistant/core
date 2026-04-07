"""The Jellyfin integration."""

from collections.abc import Callable
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.device_registry import (
    EVENT_DEVICE_REGISTRY_UPDATED,
    EventDeviceRegistryUpdatedData,
)
from homeassistant.helpers.typing import ConfigType

from .client_wrapper import CannotConnect, InvalidAuth, create_client, validate_input
from .const import CONF_CLIENT_DEVICE_ID, DEFAULT_NAME, DOMAIN, PLATFORMS
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

    _migrate_device_identifiers(hass, entry, coordinator.server_id, coordinator.user_id)

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


async def async_unload_entry(hass: HomeAssistant, entry: JellyfinConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _migrate_device_identifiers(
    hass: HomeAssistant, entry: JellyfinConfigEntry, server_id: str, user_id: str
) -> None:
    """Migrate bare client device identifiers to the fully-scoped format.

    Before this integration tracked devices persistently, client devices were
    registered as (DOMAIN, device_id) with no server or user scoping. These
    are updated in place to (DOMAIN, {server_id}-{user_id}-{device_id}),
    preserving area assignments and name overrides.
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
            # Bare device_id with no prefix.
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
