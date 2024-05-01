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
    TankerkoenigRateLimitError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ID, CONF_API_KEY, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_FUEL_TYPES, CONF_STATIONS

_LOGGER = logging.getLogger(__name__)

TankerkoenigConfigEntry = ConfigEntry["TankerkoenigDataUpdateCoordinator"]


class TankerkoenigDataUpdateCoordinator(DataUpdateCoordinator[dict[str, PriceInfo]]):
    """Get the latest data from the API."""

    config_entry: TankerkoenigConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
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

        self._selected_stations: list[str] = self.config_entry.data[CONF_STATIONS]
        self.stations: dict[str, Station] = {}
        self.fuel_types: list[str] = self.config_entry.data[CONF_FUEL_TYPES]
        self.show_on_map: bool = self.config_entry.options[CONF_SHOW_ON_MAP]

        self._tankerkoenig = Tankerkoenig(
            api_key=self.config_entry.data[CONF_API_KEY],
            session=async_get_clientsession(hass),
        )

    async def async_setup(self) -> None:
        """Set up the tankerkoenig API."""
        for station_id in self._selected_stations:
            try:
                station = await self._tankerkoenig.station_details(station_id)
            except TankerkoenigInvalidKeyError as err:
                _LOGGER.debug(
                    "invalid key error occur during setup of station %s %s",
                    station_id,
                    err,
                )
                raise ConfigEntryAuthFailed(err) from err
            except TankerkoenigConnectionError as err:
                _LOGGER.debug(
                    "connection error occur during setup of station %s %s",
                    station_id,
                    err,
                )
                raise ConfigEntryNotReady(err) from err
            except TankerkoenigError as err:
                _LOGGER.error("Error when adding station %s %s", station_id, err)
                continue

            self.stations[station_id] = station

        entity_reg = er.async_get(self.hass)
        for entity in er.async_entries_for_config_entry(
            entity_reg, self.config_entry.entry_id
        ):
            if entity.unique_id.split("_")[0] not in self._selected_stations:
                _LOGGER.debug("Removing obsolete entity entry %s", entity.entity_id)
                entity_reg.async_remove(entity.entity_id)

        device_reg = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(
            device_reg, self.config_entry.entry_id
        ):
            if not any(
                (ATTR_ID, station_id) in device.identifiers
                for station_id in self._selected_stations
            ):
                _LOGGER.debug("Removing obsolete device entry %s", device.name)
                device_reg.async_update_device(
                    device.id, remove_config_entry_id=self.config_entry.entry_id
                )

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
            stations = station_ids[index * 10 : (index + 1) * 10]
            try:
                data = await self._tankerkoenig.prices(stations)
            except TankerkoenigInvalidKeyError as err:
                _LOGGER.debug(
                    "invalid key error occur during update of stations %s %s",
                    stations,
                    err,
                )
                raise ConfigEntryAuthFailed(err) from err
            except TankerkoenigRateLimitError as err:
                _LOGGER.warning(
                    "API rate limit reached, consider to increase polling interval"
                )
                raise UpdateFailed(err) from err
            except (TankerkoenigError, TankerkoenigConnectionError) as err:
                _LOGGER.debug(
                    "error occur during update of stations %s %s",
                    stations,
                    err,
                )
                raise UpdateFailed(err) from err

            prices.update(data)

        return prices
