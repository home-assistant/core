"""The launch_library component."""

from __future__ import annotations

from collections.abc import Coroutine
from datetime import timedelta
import logging
from typing import Any, TypedDict

from pylaunches import PyLaunches, PyLaunchesError
from pylaunches.types import Launch, StarshipResponse

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

    upcoming_launches: DataUpdateCoordinator[list[Launch]]
    starship_events: DataUpdateCoordinator[StarshipResponse]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[LaunchLibraryData],
) -> bool:
    """Set up this integration using UI."""
    launches = PyLaunches(session=async_get_clientsession(hass), dev=True)

    def _create_coordinator(
        name: str,
        update_method: Coroutine,
    ) -> DataUpdateCoordinator[list[Any]]:
        async def _update_method():
            try:
                return await update_method
            except PyLaunchesError as ex:
                raise UpdateFailed(ex) from ex

        return DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{name}",
            update_method=_update_method,
            update_interval=timedelta(hours=1),
        )

    entry.runtime_data = LaunchLibraryData(
        starship_events=_create_coordinator(
            name="dashboard_starship",
            update_method=launches.dashboard_starship(),
        ),
        upcoming_launches=_create_coordinator(
            name="launch_upcoming",
            update_method=launches.launch_upcoming(
                filters={
                    "limit": 1,
                    "hide_recent_previous": "True",
                },
            ),
        ),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
