"""The Flashforge integration."""
from __future__ import annotations

from ffpp.Printer import Printer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .data_update_coordinator import FlashForgeDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Flashforge from a config entry."""
    printer = Printer(entry.data[CONF_IP_ADDRESS], port=entry.data[CONF_PORT])

    coordinator = FlashForgeDataUpdateCoordinator(hass, printer, entry)

    await coordinator.async_config_entry_first_refresh()

    # Save the coordinator object to be able to access it later on.
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
