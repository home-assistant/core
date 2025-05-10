"""Initialisation du package de l'intégration Frisquet Connect"""

import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from frisquet_connect.devices.frisquet_connect_coordinator import (
    FrisquetConnectCoordinator,
)
from frisquet_connect.devices.frisquet_connect_device import (
    FrisquetConnectDevice,
)
from .const import (
    DOMAIN,
    PLATFORMS,
)


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug("Initializing Device Frisquet Connect")

    try:
        site_id = entry.data.get("site_id")
        if site_id is None:
            _LOGGER.error("No site_id found - Please reconfigure the integration")
            return False

        service = FrisquetConnectDevice(
            entry.data.get("email"), entry.data.get("password")
        )
        coordinator = FrisquetConnectCoordinator(
            hass, service, entry.data.get("site_id")
        )
        await coordinator._async_refresh()

        if not coordinator.is_site_loaded:
            _LOGGER.error("Site not found")
            return False

        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.unique_id] = coordinator

        _LOGGER.debug("Pre-Initializing entities")
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _LOGGER.debug("Post-Initializing entities")
    except Exception as e:
        _LOGGER.error(f"Error during setup: {str(e)}")
        return False

    _LOGGER.debug("Device Frisquet Connect initialized")
    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Cleanup
        hass.data[DOMAIN].pop(entry.unique_id)
    return unload_ok
