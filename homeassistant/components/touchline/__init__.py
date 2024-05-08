"""Platform for Roth Touchline floor heating controller."""

from __future__ import annotations

from pytouchline_extended import PyTouchline

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import _LOGGER, DOMAIN

PLATFORMS = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Roth Touchline from a config entry."""

    host = entry.data[CONF_HOST]
    _LOGGER.debug(
        "Host: %s",
        host,
    )

    py_touchline = PyTouchline(url=host)
    number_of_devices = int(
        await hass.async_add_executor_job(py_touchline.get_number_of_devices)
    )

    _LOGGER.debug(
        "Number of devices found: %s",
        number_of_devices,
    )

    if not number_of_devices:
        raise ConfigEntryNotReady
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = py_touchline
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
