"""The yale_smart_alarm component."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import DOMAIN, LOGGER, PLATFORMS
from .coordinator import YaleDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Yale from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    title = entry.title

    coordinator = YaleDataUpdateCoordinator(hass, entry=entry)

    if not await hass.async_add_executor_job(coordinator.get_updates):
        raise ConfigEntryAuthFailed

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    LOGGER.debug("Loaded entry for %s", title)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    title = entry.title
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        LOGGER.debug("Unloaded entry for %s", title)
        return unload_ok

    return False
