"""The launch_library component."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import TypedDict

from pylaunches import PyLaunches, PyLaunchesException
from pylaunches.objects.launch import Launch
from pylaunches.objects.starship import StarshipResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


class LaunchLibraryData(TypedDict):
    """Typed dict representation of data returned from pylaunches."""

    upcoming_launches: list[Launch]
    starship_events: StarshipResponse


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""

    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    launches = PyLaunches(session)

    async def async_update() -> LaunchLibraryData:
        try:
            return LaunchLibraryData(
                upcoming_launches=await launches.upcoming_launches(),
                starship_events=await launches.starship_events(),
            )
        except PyLaunchesException as ex:
            raise UpdateFailed(ex) from ex

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update,
        update_interval=timedelta(hours=1),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN]
    return unload_ok
