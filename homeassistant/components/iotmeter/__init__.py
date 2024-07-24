"""IoTMeter integration for Home Assistant."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import IotMeterDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

PLATFORMS = [Platform.SENSOR]  # Platform.NUMBER


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IoTMeter from a config entry."""
    _LOGGER.debug("Setting up IoTMeter integration")
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}  # Ensure that the domain is a dictionary

    ip_address = entry.data.get("ip_address")
    port = entry.data.get("port", 8000)  # Default to port 8000 if not set

    _coordinator = IotMeterDataUpdateCoordinator(hass, ip_address, port)
    await _coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN] = {
        "coordinator": _coordinator,
        "ip_address": ip_address,
        "port": port,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    ip_address = entry.data.get("ip_address", entry.data.get("ip_address"))
    port = entry.data.get("port", entry.data.get("port", 8000))
    _coordinator = hass.data[DOMAIN]["coordinator"]
    _coordinator.update_ip_port(ip_address, port)
    await _coordinator.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle unloading of an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.pop(DOMAIN)
    return unload_ok
