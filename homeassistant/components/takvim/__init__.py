"""The Takvim integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import PrayerTimesCoordinator

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Takvim from a config entry."""
    coordinator = PrayerTimesCoordinator(hass, entry.data["district_id"])

    # Initial fetch when Home Assistant starts
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # ⭐ OPTIONAL: Daily refresh at midnight (keine Logik geändert, nur bereinigt)
    # remove_midnight_listener = async_track_time_change(
    #     hass,
    #     lambda now: hass.async_create_task(coordinator.async_request_refresh()),
    #     hour=0,
    #     minute=0,
    #     second=0,
    # )
    # entry.async_on_unload(remove_midnight_listener)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    success = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if success:
        hass.data[DOMAIN].pop(entry.entry_id)
    return success
