"""Support for the Transmission BitTorrent client API."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .client import TransmissionClientCoordinator
from .const import (
    DOMAIN,
    SERVICE_ADD_TORRENT,
    SERVICE_REMOVE_TORRENT,
    SERVICE_START_TORRENT,
    SERVICE_STOP_TORRENT,
)

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Transmission Component."""

    coordinator = TransmissionClientCoordinator(hass, config_entry)
    if not await coordinator.async_setup():
        return False
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Transmission Entry from config_entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_ADD_TORRENT)
            hass.services.async_remove(DOMAIN, SERVICE_REMOVE_TORRENT)
            hass.services.async_remove(DOMAIN, SERVICE_START_TORRENT)
            hass.services.async_remove(DOMAIN, SERVICE_STOP_TORRENT)
            del hass.data[DOMAIN]

    return unload_ok
