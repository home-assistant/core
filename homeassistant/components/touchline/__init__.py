"""The touchline component."""

import logging

from pytouchline_extended import PyTouchline

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .data import TouchlineConfigEntry, TouchlineData

PLATFORMS = [Platform.CLIMATE]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: TouchlineConfigEntry) -> None:
    """Set up touchline from a config entry."""
    host = entry.data[CONF_HOST]
    _LOGGER.debug(
        "Touchline entry id: %s Unique id: %s", entry.entry_id, entry.unique_id
    )
    py_touchline = PyTouchline(url=host)
    try:
        number_of_devices = int(
            await hass.async_add_executor_job(py_touchline.get_number_of_devices)
        )
    except (OSError, ConnectionError, TimeoutError) as err:
        raise ConfigEntryNotReady(
            f"Error while connecting to Touchline controller at {host}"
        ) from err

    entry.runtime_data = TouchlineData(
        touchline=py_touchline, number_of_devices=number_of_devices
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a touchline config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
