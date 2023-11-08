"""The Vogel's MotionMount integration."""
from __future__ import annotations

import motionmount

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import MotionMountCoordinator

PLATFORMS: list[Platform] = [
    Platform.NUMBER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Vogel's MotionMount from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    # Create API instance
    mm = motionmount.MotionMount(entry.data[CONF_HOST], entry.data[CONF_PORT])
    coordinator = MotionMountCoordinator(hass, mm)
    mm.add_listener(coordinator.motionmount_callback)

    # Validate the API connection
    try:
        await mm.connect()
        await coordinator.async_config_entry_first_refresh()
    except Exception as ex:
        raise ConfigEntryNotReady(
            f"Failed to connect to {entry.data[CONF_HOST]}"
        ) from ex

    # Store an API object for your platforms to access
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.mm.remove_listener(coordinator.motionmount_callback)
        await coordinator.mm.disconnect()

    return unload_ok
