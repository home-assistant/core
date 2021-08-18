"""The Rainforest Eagle-200 integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant

from . import data
from .const import CONF_CLOUD_ID, CONF_INSTALL_CODE, DOMAIN

PLATFORMS = ("sensor",)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Rainforest Eagle-200 from a config entry."""
    coordinator = data.EagleDataCoordinator(
        hass,
        entry.data[CONF_TYPE],
        entry.data[CONF_CLOUD_ID],
        entry.data[CONF_INSTALL_CODE],
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
