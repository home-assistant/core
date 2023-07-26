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
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATOR: coordinator,
        AUTH: auth,
    }
    await hass.config_entries.async_forward_entry_setups(entry, list(PLATFORMS))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
