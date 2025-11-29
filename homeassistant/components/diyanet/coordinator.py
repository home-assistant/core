"""Coordinator for Diyanet integration."""

from collections.abc import Callable
from datetime import datetime
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DiyanetApiClient, DiyanetConnectionError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DiyanetCoordinator(DataUpdateCoordinator[dict]):
    """Diyanet data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: DiyanetApiClient,
        location_id: int,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        # Set update interval to None - we'll use scheduled updates
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=None,
            config_entry=config_entry,
        )
        self.client = client
        self.location_id = location_id
        self._unsub_timer: Callable[[], None] | None = None

    async def async_setup(self) -> None:
        """Set up the coordinator with daily updates at 00:15."""
        # Schedule daily update at 00:15
        self._unsub_timer = async_track_time_change(
            self.hass,
            self._scheduled_update,
            hour=0,
            minute=15,
            second=0,
        )

    async def _scheduled_update(self, now: datetime) -> None:
        """Handle scheduled update."""
        _LOGGER.debug("Running scheduled prayer times update at %s", now)
        await self.async_request_refresh()

    def shutdown(self) -> None:
        """Unload the coordinator."""
        if self._unsub_timer:
            self._unsub_timer()

    async def _async_update_data(self) -> dict:
        """Fetch data from Diyanet API."""
        try:
            _LOGGER.debug("Fetching prayer times for location %s", self.location_id)
            data = await self.client.get_prayer_times(self.location_id)
        except DiyanetConnectionError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        else:
            _LOGGER.debug("Prayer times updated successfully")
            return data
