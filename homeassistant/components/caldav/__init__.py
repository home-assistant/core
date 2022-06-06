"""The caldav component."""
from __future__ import annotations

import logging

import caldav

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Caldav component."""
    calendars = await async_caldav_connect(hass, entry.data)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = calendars
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def update_listener(hass, config_entry):
    """Reload device tracker if change option."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_caldav_connect(hass, data_entry):
    """Connect to caldav server."""
    client = caldav.DAVClient(
        url=data_entry[CONF_URL],
        username=data_entry[CONF_USERNAME],
        password=data_entry[CONF_PASSWORD],
        ssl_verify_cert=data_entry[CONF_VERIFY_SSL],
    )

    try:
        principal = await hass.async_add_job(client.principal)
        return await hass.async_add_job(principal.calendars)
    except Exception as error:  # pylint:disable=broad-except
        raise ConfigEntryNotReady() from error
