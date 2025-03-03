"""Platform for Roth Touchline floor heating controller."""

from __future__ import annotations

from pytouchline_extended import PyTouchline

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import _LOGGER, DOMAIN

PLATFORMS = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Roth Touchline from a config entry."""
    host = entry.data.get("host")
    _LOGGER.debug("Setting up Roth Touchline integration for host: %s", host)

    if not host:
        _LOGGER.error("No host found in the config entry")
        return False  # Abort setup

    # Initialize PyTouchline instance and store runtime data
    try:
        py_touchline = PyTouchline(url=host)
        number_of_devices = await hass.async_add_executor_job(
            py_touchline.get_number_of_devices
        )

        if number_of_devices == 0:
            _LOGGER.error("No devices found on Roth Touchline at %s", host)
            return False  # Abort setup

        _LOGGER.debug(
            "Discovered %d devices on Roth Touchline at %s", number_of_devices, host
        )

        # Store API instance and device count in hass.data for reuse in platforms
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            "api": py_touchline,
            "device_count": number_of_devices,
        }

    except ConnectionError as err:
        _LOGGER.error("Failed to connect to Roth Touchline at %s: %s", host, err)
        return False  # Abort setup

    # Forward setup to platform(s)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        _LOGGER.debug("Unloaded Roth Touchline integration")
        # Remove stored API instance from hass.data
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
