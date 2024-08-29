"""The Google Photos integration."""

from __future__ import annotations

from aiohttp import ClientError, ClientResponseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow

from . import api
from .const import DOMAIN

PLATFORMS: list[Platform] = []

type GooglePhotosConfigEntry = ConfigEntry[api.AsyncConfigEntryAuth]

__all__ = [
    "DOMAIN",
]


async def async_setup_entry(
    hass: HomeAssistant, entry: GooglePhotosConfigEntry
) -> bool:
    """Set up Google Photos from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    auth = api.AsyncConfigEntryAuth(hass, session)
    try:
        await auth.async_get_access_token()
    except ClientResponseError as err:
        raise ConfigEntryNotReady from err
    except ClientError as err:
        raise ConfigEntryNotReady from err
    entry.runtime_data = auth
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GooglePhotosConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
