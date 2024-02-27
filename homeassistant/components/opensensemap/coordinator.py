"""Accessing OpenSenseMapApi."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from opensensemap_api import _TITLES, OpenSenseMap
from opensensemap_api.exceptions import OpenSenseMapError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER, SensorTypeId


class OpenSenseMapDataUpdateCoordinator(DataUpdateCoordinator[OpenSenseMap]):
    """My custom coordinator."""

    def __init__(
        self, hass: HomeAssistant, station_api: OpenSenseMap, config_entry: ConfigEntry
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            # Name of the data. For logging purposes.
            name=config_entry.data[CONF_NAME],
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(minutes=10),
        )
        self.station_api = station_api

        async def _async_update_data(self)-> OpenSenseMap:
        """Fetch data from API endpoint."""
        try:
            await self.station_api.get_data()
        except OpenSenseMapError as err:
            LOGGER.error("Unable to fetch data: %s", err)
            raise UpdateFailed from err

        return self.station_api
