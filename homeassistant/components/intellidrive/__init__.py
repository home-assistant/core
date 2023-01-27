"""The Intellidrive integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .device import ReisingerSlidingDoorDevice

#  List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Intellidrive from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    #  1. Create API instance
    #  2. Validate the API connection (and authentication)
    #  3. Store an API object for your platforms to access
    hub = ReisingerSlidingDoorDevice(
        str(entry.data.get("host")), str(entry.data.get("token"))
    )

    if not await hub.authenticate():
        return False

    hass.data[DOMAIN][entry.entry_id] = hub

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
