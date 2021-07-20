"""The Anthem A/V Receivers integration."""
from __future__ import annotations

import logging

import anthemav

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import ANTHEMAV_UDATE_SIGNAL, DOMAIN

PLATFORMS = ["media_player"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Anthem A/V Receivers from a config entry."""

    @callback
    def async_anthemav_update_callback(message):
        """Receive notification from transport that new data exists."""
        _LOGGER.debug("Received update callback from AVR: %s", message)
        async_dispatcher_send(hass, f"{ANTHEMAV_UDATE_SIGNAL}_{entry.data[CONF_NAME]}")

    try:
        avr = await anthemav.Connection.create(
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            update_callback=async_anthemav_update_callback,
        )

    except Exception as err:
        raise ConfigEntryNotReady from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = avr

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    avr = hass.data[DOMAIN][entry.entry_id]

    if avr is not None:
        _LOGGER.debug("Close avr connection")
        avr.close()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when it changed."""
    await hass.config_entries.async_reload(entry.entry_id)
