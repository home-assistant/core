"""The power_hub integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import BitvisDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [Platform.SENSOR]

type BitvisConfigEntry = ConfigEntry[BitvisDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: BitvisConfigEntry) -> bool:
    """Set up power_hub from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    _LOGGER.debug("Setting up Bitvis Power Hub at %s:%s", host, port)

    coordinator = BitvisDataUpdateCoordinator(hass, entry, host, port)

    try:
        await coordinator.async_start()
    except OSError as err:
        raise ConfigEntryNotReady(
            f"Failed to start UDP listener on port {port}"
        ) from err

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BitvisConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, _PLATFORMS):
        await entry.runtime_data.async_stop()
    return unload_ok
