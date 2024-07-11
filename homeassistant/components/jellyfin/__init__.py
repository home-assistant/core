"""The Jellyfin integration."""

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .client_wrapper import CannotConnect, InvalidAuth, create_client, validate_input
from .const import CONF_CLIENT_DEVICE_ID, DOMAIN, PLATFORMS
from .coordinator import JellyfinDataUpdateCoordinator, SessionsDataUpdateCoordinator
from .models import JellyfinData


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Jellyfin from a config entry."""
    hass.data.setdefault(DOMAIN, {})

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

    coordinators: dict[str, JellyfinDataUpdateCoordinator[Any]] = {
        "sessions": SessionsDataUpdateCoordinator(
            hass, client, server_info, entry.data[CONF_CLIENT_DEVICE_ID], user_id
        ),
    }

    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = JellyfinData(
        client_device_id=entry.data[CONF_CLIENT_DEVICE_ID],
        jellyfin_client=client,
        coordinators=coordinators,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        data.jellyfin_client.stop()

    return unloaded


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove device from a config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data.coordinators["sessions"]

    return not device_entry.identifiers.intersection(
        (
            (DOMAIN, coordinator.server_id),
            *((DOMAIN, device_id) for device_id in coordinator.device_ids),
        )
    )
