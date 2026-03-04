"""DataUpdateCoordinator for the launch_library integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TypedDict

from pylaunches import PyLaunches, PyLaunchesError
from pylaunches.types import Launch, StarshipResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class LaunchLibraryData(TypedDict):
    """Typed dict representation of data returned from pylaunches."""

    upcoming_launches: list[Launch]
    starship_events: StarshipResponse


class LaunchLibraryCoordinator(DataUpdateCoordinator[LaunchLibraryData]):
    """Class to manage fetching Launch Library data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(hours=1),
        )
        session = async_get_clientsession(hass)
        self._launches = PyLaunches(session)

    async def _async_update_data(self) -> LaunchLibraryData:
        """Fetch data from Launch Library."""
        try:
            return LaunchLibraryData(
                upcoming_launches=await self._launches.launch_upcoming(
                    filters={"limit": 1, "hide_recent_previous": "True"},
                ),
                starship_events=await self._launches.dashboard_starship(),
            )
        except PyLaunchesError as ex:
            raise UpdateFailed(ex) from ex
