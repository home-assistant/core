"""The Internet Printing Protocol (IPP) integration."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from .const import CONF_BASE_PATH, DOMAIN
from .coordinator import IPPDataUpdateCoordinator

PLATFORMS = [SENSOR_DOMAIN]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IPP from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    if not coordinator:
        # Create IPP instance for this entry
        coordinator = IPPDataUpdateCoordinator(
            hass,
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            base_path=entry.data[CONF_BASE_PATH],
            tls=entry.data[CONF_SSL],
            verify_ssl=entry.data[CONF_VERIFY_SSL],
        )
        hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
