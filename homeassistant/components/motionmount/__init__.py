"""The Vogel's MotionMount integration."""
from __future__ import annotations

import motionmount

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import MotionMountCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Vogel's MotionMount from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    # Create API instance
    coordinator = MotionMountCoordinator(hass)
    mm = motionmount.MotionMount(
        entry.data[CONF_HOST], entry.data[CONF_PORT], coordinator._motionmount_callback
    )
    coordinator.mm = mm

    # Validate the API connection
    await mm.connect()

    # Store an API object for your platforms to access
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.mm.disconnect()

    return unload_ok
