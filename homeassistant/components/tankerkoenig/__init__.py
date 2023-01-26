"""Ask tankerkoenig.de for petrol price information."""
from __future__ import annotations

from datetime import timedelta
import logging
from math import ceil

import pytankerkoenig
from requests.exceptions import RequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ID, CONF_API_KEY, CONF_SHOW_ON_MAP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import CONF_FUEL_TYPES, CONF_STATIONS, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set a tankerkoenig configuration entry up."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator = TankerkoenigDataUpdateCoordinator(
        hass,
        entry,
        _LOGGER,
        name=entry.unique_id or DOMAIN,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )

    try:
        setup_ok = await hass.async_add_executor_job(coordinator.setup)
    except RequestException as err:
        raise ConfigEntryNotReady from err
    if not setup_ok:
        _LOGGER.error("Could not setup integration")
        return False

    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Tankerkoenig config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


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


class TankerkoenigCoordinatorEntity(CoordinatorEntity):
    """Tankerkoenig base entity."""

    def __init__(
        self, coordinator: TankerkoenigDataUpdateCoordinator, station: dict
    ) -> None:
        """Initialize the Tankerkoenig base entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(ATTR_ID, station["id"])},
            name=f"{station['brand']} {station['street']} {station['houseNumber']}",
            model=station["brand"],
            configuration_url="https://www.tankerkoenig.de",
            entry_type=DeviceEntryType.SERVICE,
        )
