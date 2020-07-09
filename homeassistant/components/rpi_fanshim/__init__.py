"""The RPi Pimoroni Fan Shim integration."""
import asyncio

from fanshim import FanShim
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["light"]


class FanShimHub:
    """Initialize the Fan Shim Hub class."""

    def __init__(self):
        """Initialize the class."""
        self.hub = None


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the RPi Pimoroni Fan Shim component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up RPi Pimoroni Fan Shim from a config entry."""
    fanshim = FanShimHub()
    fanshim.hub = FanShim()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = fanshim

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
