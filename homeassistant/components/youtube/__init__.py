"""Support for YouTube."""

from __future__ import annotations

from aiohttp.client_exceptions import ClientError, ClientResponseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
import homeassistant.helpers.device_registry as dr

from .api import AsyncConfigEntryAuth
from .const import AUTH, COORDINATOR, DOMAIN
from .coordinator import YouTubeDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up YouTube from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    auth = AsyncConfigEntryAuth(hass, session)
    try:
        await auth.check_and_refresh_token()
    except ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed(
                "OAuth session is not valid, reauth required"
            ) from err
        raise ConfigEntryNotReady from err
    except ClientError as err:
        raise ConfigEntryNotReady from err
    coordinator = YouTubeDataUpdateCoordinator(hass, auth)

    await coordinator.async_config_entry_first_refresh()

    await delete_devices(hass, entry, coordinator)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATOR: coordinator,
        AUTH: auth,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def delete_devices(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: YouTubeDataUpdateCoordinator
) -> None:
    """Delete all devices created by integration."""
    channel_ids = list(coordinator.data)
    device_registry = dr.async_get(hass)
    dev_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    for dev_entry in dev_entries:
        if any(identifier[1] in channel_ids for identifier in dev_entry.identifiers):
            device_registry.async_update_device(
                dev_entry.id, remove_config_entry_id=entry.entry_id
            )
