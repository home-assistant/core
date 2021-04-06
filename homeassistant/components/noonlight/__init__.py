"""The Noonlight integration."""
from __future__ import annotations

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_API_TOKEN, CONF_ADDRESS, CONF_PIN

from .const import _LOGGER, DATA_NOONLIGHT_CONFIG, DOMAIN

DOMAIN = "noonlight"
PLATFORMS = ["alarm_control_panel"]

from noonlight_homeassistant import noonlight


async def async_setup(hass, config):

    hass.data[DATA_NOONLIGHT_CONFIG] = config.get(DOMAIN, {})
    _LOGGER.info("The 'noonlight' component is ready!")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Noonlight from a config entry."""

    data = NoonlightData(hass, entry)

    hass.data[DOMAIN] = data

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


class NoonlightData:
    def __init__(self, hass, entry):
        """Initialize the Noonlight data object."""
        self.hass = hass
        self.entry = entry


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    # if unload_ok:
    #    hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
