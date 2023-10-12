"""The Tankerkoenig update coordinator."""
from __future__ import annotations

from datetime import timedelta
import logging
from math import ceil

import pytankerkoenig

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_FUEL_TYPES, CONF_STATIONS

_LOGGER = logging.getLogger(__name__)


class TankerkoenigDataUpdateCoordinator(DataUpdateCoordinator):
    """Get the latest data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        logger: logging.Logger,
        name: str,
        update_interval: int,
    ) -> None:
        """Initialize the data object."""

        super().__init__(
            hass=hass,
            logger=logger,
            name=name,
            update_interval=timedelta(minutes=update_interval),
        )

        self._api_key: str = entry.data[CONF_API_KEY]
        self._selected_stations: list[str] = entry.data[CONF_STATIONS]
        self.stations: dict[str, dict] = {}
        self.fuel_types: list[str] = entry.data[CONF_FUEL_TYPES]
        self.show_on_map: bool = entry.options[CONF_SHOW_ON_MAP]

    def setup(self) -> bool:
        """Set up the tankerkoenig API."""
        for station_id in self._selected_stations:
            try:
                station_data = pytankerkoenig.getStationData(self._api_key, station_id)
            except pytankerkoenig.customException as err:
                if any(x in str(err).lower() for x in ("api-key", "apikey")):
                    raise ConfigEntryAuthFailed(err) from err
                station_data = {
                    "ok": False,
                    "message": err,
                    "exception": True,
                }

            if not station_data["ok"]:
                _LOGGER.error(
                    "Error when adding station %s:\n %s",
                    station_id,
                    station_data["message"],
                )
                continue
            self.add_station(station_data["station"])
        if len(self.stations) > 10:
            _LOGGER.warning(
                "Found more than 10 stations to check. "
                "This might invalidate your api-key on the long run. "
                "Try using a smaller radius"
            )
        return True

    async def _async_update_data(self) -> dict:
        """Get the latest data from tankerkoenig.de."""
        _LOGGER.debug("Fetching new data from tankerkoenig.de")
        station_ids = list(self.stations)

        prices = {}

        # The API seems to only return at most 10 results, so split the list in chunks of 10
        # and merge it together.
        for index in range(ceil(len(station_ids) / 10)):
            data = await self.hass.async_add_executor_job(
                pytankerkoenig.getPriceList,
                self._api_key,
                station_ids[index * 10 : (index + 1) * 10],
            )

            _LOGGER.debug("Received data: %s", data)
            if not data["ok"]:
                raise UpdateFailed(data["message"])
            if "prices" not in data:
                raise UpdateFailed(
                    "Did not receive price information from tankerkoenig.de"
                )
            prices.update(data["prices"])
        return prices

    def add_station(self, station: dict):
        """Add fuel station to the entity list."""
        station_id = station["id"]
        if station_id in self.stations:
            _LOGGER.warning(
                "Sensor for station with id %s was already created", station_id
            )
            return

        self.stations[station_id] = station
        _LOGGER.debug("add_station called for station: %s", station)
