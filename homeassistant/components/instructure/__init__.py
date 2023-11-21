"""The canvas integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import CanvasUpdateCoordinator

from .const import DOMAIN, ASSIGNMENTS_KEY, ANNOUNCEMENTS_KEY, CONVERSATIONS_KEY

from .canvas_api import CanvasAPI


# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up canvas from a config entry."""
    # Why do we want to have [entry.entry_id] ?
    # Do we assume multiple Canvas users on the same house?
    # Too long
    # I think this is unnecessary, only reducing readability: hass.data[DOMAIN][entry.entry_id]["entities"]
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {})
    hass.data[DOMAIN][entry.entry_id].setdefault("entities", {})
    hass.data[DOMAIN][entry.entry_id]["entities"].setdefault(ASSIGNMENTS_KEY, {})
    hass.data[DOMAIN][entry.entry_id]["entities"].setdefault(ANNOUNCEMENTS_KEY, {})
    hass.data[DOMAIN][entry.entry_id]["entities"].setdefault(CONVERSATIONS_KEY, {})

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
