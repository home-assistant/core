"""The Fronius integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[str] = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up fronius from a config entry."""
    fronius = FroniusSolarNet(hass, entry)
    await fronius.init_devices()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = fronius
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class FroniusSolarNet:
    """The FroniusSolarNet class manages update coordinators."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize FroniusSolarNet class."""
        self.hass = hass
        self.host: str = entry.data[CONF_HOST]

    async def init_devices(self) -> None:
        """Initialize DataUpdateCoordinators for SolarNet devices."""
        raise NotImplementedError
