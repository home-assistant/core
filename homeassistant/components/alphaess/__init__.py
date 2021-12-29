"""The AlphaEss integration."""
from __future__ import annotations

import logging

from alphaess import alphaess

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import AlphaESSDataUpdateCoordinator, async_update_options

PLATFORMS = [Platform.SENSOR]

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Alpha ESS from a config entry."""

    client = alphaess.alphaess()
    client.username = entry.data[CONF_USERNAME]
    client.password = entry.data[CONF_PASSWORD]

    coordinator = AlphaESSDataUpdateCoordinator(hass, client=client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True
