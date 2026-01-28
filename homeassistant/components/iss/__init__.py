"""The iss component."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_PEOPLE_UPDATE_HOURS,
    CONF_POSITION_UPDATE_SECONDS,
    DEFAULT_PEOPLE_UPDATE_HOURS,
    DEFAULT_POSITION_UPDATE_SECONDS,
    DOMAIN,
)
from .coordinator.people import IssPeopleCoordinator
from .coordinator.position import IssPositionCoordinator
from .coordinator.tle import IssTleCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    hass.data.setdefault(DOMAIN, {})

    #
    # TLE Coordinator - Fetches orbital data infrequently
    #
    tle_coordinator = IssTleCoordinator(
        hass,
        config_entry=entry,
        # TLE updates are hardcoded to daily - no need for user configuration
        update_interval=timedelta(hours=24),
    )

    # First refresh
    await tle_coordinator.async_config_entry_first_refresh()

    # Add a dummy listener to keep the coordinator alive for periodic updates
    tle_coordinator.async_add_listener(lambda: None)

    #
    # Position Coordinator - Calculates position from TLE data
    #
    position_update_seconds = entry.options.get(
        CONF_POSITION_UPDATE_SECONDS, DEFAULT_POSITION_UPDATE_SECONDS
    )
    position_coordinator = IssPositionCoordinator(
        hass,
        config_entry=entry,
        tle_coordinator=tle_coordinator,
        update_interval=timedelta(seconds=position_update_seconds),
    )

    await position_coordinator.async_config_entry_first_refresh()

    #
    # People-in-Space Coordinator - Fetches from open-notify API
    #
    people_coordinator = IssPeopleCoordinator(
        hass,
        config_entry=entry,
        update_interval=timedelta(
            hours=entry.options.get(
                CONF_PEOPLE_UPDATE_HOURS, DEFAULT_PEOPLE_UPDATE_HOURS
            )
        ),
    )

    await people_coordinator.async_config_entry_first_refresh()

    #
    # Store all coordinators
    #
    hass.data[DOMAIN][entry.entry_id] = {
        "tle_coordinator": tle_coordinator,
        "position_coordinator": position_coordinator,
        "people_coordinator": people_coordinator,
    }

    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        if DOMAIN in hass.data:
            hass.data[DOMAIN].pop(entry.entry_id, None)
            if not hass.data[DOMAIN]:
                del hass.data[DOMAIN]
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
