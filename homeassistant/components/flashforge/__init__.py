"""The FlashForge 3D Printer integration."""
from __future__ import annotations

from ffpp.Printer import Printer

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DOMAIN, SCAN_INTERVAL
from .data_update_coordinator import FlashForgeDataUpdateCoordinator

PLATFORMS = [SENSOR_DOMAIN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FlashForge 3D Printer from a config entry."""
    printer = Printer(entry.data[CONF_IP_ADDRESS], port=entry.data[CONF_PORT])
    # await printer.updateMachineInfo()
    # printer = entry.data[CONF_OBJECT]

    hass.data.setdefault(DOMAIN, {})

    coordinator = FlashForgeDataUpdateCoordinator(hass, printer, entry, SCAN_INTERVAL)

    await coordinator.async_config_entry_first_refresh()

    # Save the printer, and coordinator object to be able to access it later on.
    hass.data[DOMAIN][entry.entry_id] = {
        "printer": printer,
        "coordinator": coordinator,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
