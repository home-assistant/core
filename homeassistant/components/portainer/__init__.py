"""The Portainer integration."""

import logging

from aiohttp import ClientResponseError
from aiotainer.client import PortainerClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

from . import api
from .coordinator import PortainerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]

type PortainerConfigEntry = ConfigEntry[PortainerDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PortainerConfigEntry) -> bool:
    """Set up this integration using UI."""
    client_session = aiohttp_client.async_get_clientsession(hass, False)
    api_api = api.AsyncConfigEntryAuth(client_session, entry)
    portainer_api = PortainerClient(api_api)
    try:
        await api_api.async_get_access_token()
    except ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed from err
        raise ConfigEntryNotReady from err

    coordinator = PortainerDataUpdateCoordinator(hass, portainer_api, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PortainerConfigEntry) -> bool:
    """Handle unload of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
