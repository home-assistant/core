"""The touchline component."""

from __future__ import annotations

import logging

from pytouchline_extended import PyTouchline

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

PLATFORMS = [Platform.CLIMATE]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up touchline from a config entry."""
    host = entry.data[CONF_HOST]
    _LOGGER.debug("Touchline entry id: %s", entry.entry_id)
    try:
        py_touchline = PyTouchline(url=host)
        number_of_devices = int(
            await hass.async_add_executor_job(py_touchline.get_number_of_devices)
        )
    except (OSError, ConnectionError, TimeoutError) as err:
        _LOGGER.warning(
            "Error while connecting to Touchline controller at %s", host, exc_info=True
        )
        raise ConfigEntryNotReady(
            f"Error while connecting to Touchline controller at {host}"
        ) from err

    entry.runtime_data = {
        "touchline": py_touchline,
        "number_of_devices": number_of_devices,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a touchline config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
