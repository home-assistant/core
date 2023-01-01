"""The homely integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .homely_device import HomelyHome

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up homely from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    homely_home = HomelyHome(hass, entry)
    await homely_home.setup()
    hass.data[DOMAIN][entry.entry_id] = homely_home

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # set up notify platform, no entry support for notify component yet,
    # have to use discovery to load platform.
    # hass.async_create_task(
    #     discovery.async_load_platform(
    #         hass,
    #         Platform.NOTIFY,
    #         DOMAIN,
    #         {CONF_NAME: DOMAIN},
    #         hass.data[DATA_HASS_CONFIG],
    #     )
    # )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
