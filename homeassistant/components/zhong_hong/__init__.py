"""ZhongHong HVAC Integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import PLATFORMS
from .coordinator import ZhongHongDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

type ZhongHongConfigEntry = ConfigEntry[ZhongHongDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ZhongHongConfigEntry) -> bool:
    """Set up ZhongHong from a config entry."""
    coordinator = ZhongHongDataUpdateCoordinator(hass, entry)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Error connecting to ZhongHong gateway: %s", err)
        raise ConfigEntryNotReady(
            f"Unable to connect to ZhongHong gateway: {err}"
        ) from err

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZhongHongConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = entry.runtime_data
        await coordinator.async_shutdown()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ZhongHongConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
