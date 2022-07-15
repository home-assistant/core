"""The aladdin_connect component."""
import asyncio
import logging
from typing import Final

from AIOAladdinConnect import AladdinConnectClient
from aiohttp import ClientConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CLIENT_ID, DOMAIN

_LOGGER: Final = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    acc = AladdinConnectClient(
        username, password, async_get_clientsession(hass), CLIENT_ID
    )
    try:
        if not await acc.login():
            raise ConfigEntryAuthFailed("Incorrect Password")
    except (ClientConnectionError, asyncio.TimeoutError) as ex:
        raise ConfigEntryNotReady("Can not connect to host") from ex

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = acc
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
