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

from .const import DOMAIN, PRINC_CALENDARS, UNSUB_LISTENER

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Caldav component."""
    url = entry.data[CONF_URL]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    verify_ssl = entry.data[CONF_VERIFY_SSL]

    client = caldav.DAVClient(url, None, username, password, ssl_verify_cert=verify_ssl)

    principal = await hass.async_add_executor_job(client.principal)
    if not principal:
        raise ConfigEntryNotReady()
    calendars = await hass.async_add_executor_job(principal.calendars)

    unsub_listener = entry.add_update_listener(update_listener)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        PRINC_CALENDARS: calendars,
        UNSUB_LISTENER: unsub_listener,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    hass.data[DOMAIN][config_entry.entry_id][UNSUB_LISTENER]()
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def update_listener(hass, config_entry):
    """Reload device tracker if change option."""
    await hass.config_entries.async_reload(config_entry.entry_id)
