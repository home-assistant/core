"""The nsw_fuel_station component."""
import logging

from nsw_fuel import FuelCheckClient, FuelCheckError

from homeassistant.components.nsw_fuel_station.const import (
    DATA_NSW_FUEL_STATION, MIN_TIME_BETWEEN_UPDATES, DATA_ATTR_CLIENT,
    DATA_ATTR_REFERENCE_DATA)
from homeassistant.util import Throttle

DOMAIN = "nsw_fuel_station"

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    client = FuelCheckClient()

    reference_data = SharedReferenceData(client)
    reference_data.update()

    hass.data[DATA_NSW_FUEL_STATION] = {
        DATA_ATTR_CLIENT: client,
        DATA_ATTR_REFERENCE_DATA: reference_data,
    }

    return True


class SharedReferenceData():
    def __init__(self, client: FuelCheckClient):
        self._client = client
        self._data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        if self._data is None:
            try:
                self._data = self._client.get_reference_data()
            except FuelCheckError as exc:
                _LOGGER.error(
                    "Failed to fetch NSW Fuel station reference data. %s", exc
                )
                return

    def get_station_name(self, station_id: int) -> str:
        """Return the name of the station."""
        name = None
        if self._data is not None:
            name = next(
                (
                    station.name
                    for station in self._data.stations
                    if station.code == station_id
                ),
                None,
            )

        return name or f"station {station_id}"

