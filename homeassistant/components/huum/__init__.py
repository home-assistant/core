"""The Huum integration."""

from __future__ import annotations

import logging

from huum.exceptions import Forbidden, NotAuthenticated
from huum.huum import Huum

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Huum from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    huum = Huum(username, password, session=async_get_clientsession(hass))

    try:
        await huum.status()
    except (Forbidden, NotAuthenticated) as err:
        _LOGGER.error("Could not log in to Huum with given credentials")
        raise ConfigEntryNotReady(
            "Could not log in to Huum with given credentials"
        ) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = huum

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
