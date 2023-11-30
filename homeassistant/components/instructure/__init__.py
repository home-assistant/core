"""The canvas integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .canvas_api import CanvasAPI
from .const import (
    ANNOUNCEMENTS_KEY,
    ASSIGNMENTS_KEY,
    CONVERSATIONS_KEY,
    DOMAIN,
    GRADES_KEY,
    QUICK_LINKS_KEY,
)
from .coordinator import CanvasUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up canvas from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {})
    hass.data[DOMAIN][entry.entry_id].setdefault("entities", {})
    hass.data[DOMAIN][entry.entry_id]["entities"].setdefault(ASSIGNMENTS_KEY, {})
    hass.data[DOMAIN][entry.entry_id]["entities"].setdefault(ANNOUNCEMENTS_KEY, {})
    hass.data[DOMAIN][entry.entry_id]["entities"].setdefault(CONVERSATIONS_KEY, {})
    hass.data[DOMAIN][entry.entry_id]["entities"].setdefault(GRADES_KEY, {})
    hass.data[DOMAIN][entry.entry_id]["entities"].setdefault(QUICK_LINKS_KEY, {})

    api = CanvasAPI(
        f"https://{entry.data['host_prefix']}.instructure.com/api/v1",
        entry.data["access_token"],
    )
    coordinator = CanvasUpdateCoordinator(hass, entry, api)
    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
