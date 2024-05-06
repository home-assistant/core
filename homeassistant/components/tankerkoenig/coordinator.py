"""The Tankerkoenig update coordinator."""
from __future__ import annotations

from datetime import timedelta
import logging
from math import ceil

from aiotankerkoenig import (
    PriceInfo,
    Station,
    Tankerkoenig,
    TankerkoenigConnectionError,
    TankerkoenigError,
    TankerkoenigInvalidKeyError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_FUEL_TYPES, CONF_STATIONS

_LOGGER = logging.getLogger(__name__)


class TankerkoenigDataUpdateCoordinator(DataUpdateCoordinator):
    """Get the latest data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        name: str,
        update_interval: int,
    ) -> None:
        """Initialize the data object."""

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=name,
            update_interval=timedelta(minutes=update_interval),
        )

        self._selected_stations: list[str] = entry.data[CONF_STATIONS]
        self.stations: dict[str, Station] = {}
        self.fuel_types: list[str] = entry.data[CONF_FUEL_TYPES]
        self.show_on_map: bool = entry.options[CONF_SHOW_ON_MAP]

        self._tankerkoenig = Tankerkoenig(
            api_key=entry.data[CONF_API_KEY], session=async_get_clientsession(hass)
        )

    async def async_setup(self) -> None:
        """Set up the tankerkoenig API."""
        for station_id in self._selected_stations:
            try:
                station = await self._tankerkoenig.station_details(station_id)
            except TankerkoenigInvalidKeyError as err:
                raise ConfigEntryAuthFailed(err) from err
            except (TankerkoenigError, TankerkoenigConnectionError) as err:
                raise ConfigEntryNotReady(err) from err

            self.stations[station_id] = station

        if len(self.stations) > 10:
            _LOGGER.warning(
                "Found more than 10 stations to check. "
                "This might invalidate your api-key on the long run. "
                "Try using a smaller radius"
            )

    async def _async_update_data(self) -> dict[str, PriceInfo]:
        """Get the latest data from tankerkoenig.de."""
        station_ids = list(self.stations)

        prices = {}

        # The API seems to only return at most 10 results, so split the list in chunks of 10
        # and merge it together.
        for index in range(ceil(len(station_ids) / 10)):
            data = await self._tankerkoenig.prices(
                station_ids[index * 10 : (index + 1) * 10]
            )
            prices.update(data)

        return prices
