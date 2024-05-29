"""The aladdin_connect component."""

import logging
from typing import Final

from AIOAladdinConnect import AladdinConnectClient
import AIOAladdinConnect.session_manager as Aladdin
from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CLIENT_ID, DOMAIN

_LOGGER: Final = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    acc = AladdinConnectClient(
        username, password, async_get_clientsession(hass), CLIENT_ID
    )
    try:
        await acc.login()
    except (ClientError, TimeoutError, Aladdin.ConnectionError) as ex:
        raise ConfigEntryNotReady("Can not connect to host") from ex
    except Aladdin.InvalidPasswordError as ex:
        raise ConfigEntryAuthFailed("Incorrect Password") from ex

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = acc
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
