"""SMLIGHT SLZB Zigbee device integration."""

from __future__ import annotations

import logging

from pysmlight.exceptions import SmlightAuthError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN
from .coordinator import SmDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SMLIGHT Zigbee from a config entry."""
    coordinator = SmDataUpdateCoordinator(hass, entry)
    try:
        await coordinator.async_handle_setup()
    except SmlightAuthError as err:
        raise ConfigEntryAuthFailed(err) from err

    await coordinator.async_config_entry_first_refresh()
    coordinator.unique_id = format_mac(coordinator.data.info.MAC).replace(":", "")

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
