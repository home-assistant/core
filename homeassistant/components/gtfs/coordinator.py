"""Data Update coordinator for the GTFS integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_PATH, DEFAULT_REFRESH_INTERVAL
from .gtfs_helper import get_gtfs, get_next_departure

_LOGGER = logging.getLogger(__name__)


class GTFSUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for the Pronote integration."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=entry.entry_id,
            update_interval=timedelta(
                minutes=entry.data.get("refresh_interval", DEFAULT_REFRESH_INTERVAL)
            ),
        )
        self.config_entry = entry
        self.hass = hass
        self._pygtfs = ""
        self._data: dict[str, str] = {}

    async def _async_update_data(self) -> dict[str, str]:
        """Update."""
        data = self.config_entry.data
        self._pygtfs = get_gtfs(self.hass, DEFAULT_PATH, data["file"])
        self._data = {
            "schedule": self._pygtfs,
            "origin": data["origin"],
            "destination": data["destination"],
            "offset": data["offset"],
            "include_tomorrow": data["include_tomorrow"],
            "gtfs_dir": DEFAULT_PATH,
            "name": data["name"],
        }

        try:
            self._data["next_departure"] = await self.hass.async_add_executor_job(
                get_next_departure, self._data
            )
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.info("Error getting gtfs data from generic helper: %s", ex)

        return self._data
