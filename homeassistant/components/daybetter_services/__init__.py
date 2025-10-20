"""DayBetter Services integration for Home Assistant."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .daybetter_api import DayBetterApi

_LOGGER = logging.getLogger(__name__)


@dataclass
class DayBetterRuntimeData:
    """Runtime data for DayBetter Services."""

    api: DayBetterApi
    devices: list[dict[str, Any]]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DayBetter Services from a config entry."""
    _LOGGER.debug("Setting up DayBetter Services integration")

    # Initialize the API client
    token = entry.data[CONF_TOKEN]
    api = DayBetterApi(hass, token)

    # Fetch devices
    devices = await api.fetch_devices()

    # Store runtime data
    runtime_data = DayBetterRuntimeData(api=api, devices=devices)
    entry.runtime_data = runtime_data

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading DayBetter Services integration")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry.runtime_data = None

    return unload_ok