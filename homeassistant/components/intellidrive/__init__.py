"""The Intellidrive integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import ReisingerCoordinator
from .device import ReisingerSlidingDoorDeviceApi

_LOGGER = logging.getLogger(__name__)

#  List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Intellidrive from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    #  1. Create API instance
    #  2. Validate the API connection (and authentication)
    #  3. Store an API object for your platforms to access

    device_api = ReisingerSlidingDoorDeviceApi(
        str(entry.data.get("host")),
        str(entry.data.get("token")),
        async_get_clientsession(hass),
    )

    if not await device_api.authenticate():
        return False

    coordinator = ReisingerCoordinator(hass, entry, device_api)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
