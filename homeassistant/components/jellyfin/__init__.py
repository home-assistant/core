"""The Jellyfin integration."""

from contextlib import suppress
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr

from .client_wrapper import CannotConnect, InvalidAuth, create_client, validate_input
from .const import (
    CONF_CLIENT_DEVICE_ID,
    DEFAULT_NAME,
    DOMAIN,
    PLATFORMS,
    SERVER_KEY_ID,
    SERVER_KEY_NAME,
    SERVER_KEY_VERSION,
)
from .coordinator import JellyfinConfigEntry, JellyfinDataUpdateCoordinator


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
        api_server = connect_result["Servers"][0]
        # Use entry.entry_id for consistent device identification
        # Store actual server info separately
        server_info: dict[str, Any] = {
            SERVER_KEY_ID: entry.entry_id,
            SERVER_KEY_NAME: api_server.get("Name", "Jellyfin"),
            SERVER_KEY_VERSION: api_server.get("Version"),
        }
    except CannotConnect:
        # Connection failed - create fresh client to avoid partial state
        client = create_client(device_id=device_id, device_name=device_name)
        server_info = {
            SERVER_KEY_ID: entry.entry_id,
            SERVER_KEY_NAME: entry.title or "Jellyfin",
            SERVER_KEY_VERSION: None,
        }
        user_id = entry.entry_id
        connected = False
    except InvalidAuth as ex:
        raise ConfigEntryAuthFailed(ex) from ex
    else:
        connected = True

    coordinator = JellyfinDataUpdateCoordinator(
        hass, entry, client, server_info, user_id, connected
    )

    with suppress(Exception):
        await coordinator.async_config_entry_first_refresh()

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        entry_type=dr.DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, coordinator.server_id)},
        manufacturer=DEFAULT_NAME,
        name=coordinator.server_name,
        sw_version=coordinator.server_version,
    )

    entry.runtime_data = coordinator
    entry.async_on_unload(client.stop)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: JellyfinConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: JellyfinConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove device from a config entry."""
    coordinator = config_entry.runtime_data

    return not device_entry.identifiers.intersection(
        (
            (DOMAIN, coordinator.server_id),
            *((DOMAIN, device_id) for device_id in coordinator.device_ids),
        )
    )
