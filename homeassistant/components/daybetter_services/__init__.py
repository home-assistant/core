"""DayBetter Services integration setup."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import CONF_TOKEN, DEFAULT_SCAN_INTERVAL, DOMAIN, PLATFORMS
from .coordinator import DayBetterCoordinator
from .daybetter_api import DayBetterApi


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up via YAML (not used)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DayBetter from a config entry."""
    token = entry.data.get(CONF_TOKEN)

    if not token:
        return False

    api = DayBetterApi(token=token)

    coordinator = DayBetterCoordinator(
        hass,
        api,
        timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload DayBetter config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if entry_data and "api" in entry_data:
            await entry_data["api"].close()
    return unload_ok
