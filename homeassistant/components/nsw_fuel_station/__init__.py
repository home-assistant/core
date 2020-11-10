"""The nsw_fuel_station component."""
import logging
from typing import Optional

from nsw_fuel import FuelCheckClient, FuelCheckError

from homeassistant.components.nsw_fuel_station.const import (
    DATA_NSW_FUEL_STATION,
    MIN_TIME_BETWEEN_UPDATES,
    DATA_ATTR_CLIENT,
    DATA_ATTR_REFERENCE_DATA,
)
from homeassistant.util import Throttle

DOMAIN = "nsw_fuel_station"

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    client = FuelCheckClient()
    fuel_check_data = FuelCheckData(client)
    fuel_check_data.update()

    hass.data[DATA_NSW_FUEL_STATION] = fuel_check_data

    return True


class FuelCheckData:
    def __init__(self, client: FuelCheckClient):
        """An object to fetch and cache the latest fuel check data."""
        self._client = client
        self._stations = None
        self._prices = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update the internal data using the API client."""
        try:
            raw_price_data = self._client.get_fuel_prices()
            # Store prices and station details indexed by station code for
            # O(1) lookup
            self._stations = {s.code: s for s in raw_price_data.stations}
            self._prices = {
                (str(p.station_code), p.fuel_type): p.price
                for p in raw_price_data.prices
            }
        except FuelCheckError as exc:
            _LOGGER.error("Failed to fetch NSW Fuel station price data. %s", exc)
            return

    def get_fuel_price(self, station_code: int, fuel_type: str) -> Optional[float]:
        """Return the price of the given fuel type."""
        if self._prices is None:
            return None

        return self._prices.get((str(station_code), fuel_type))

    def get_station_name(self, station_code: int) -> str:
        """Return the name of the station for a given station code."""

        name = None
        if self._stations:
            station_info = self._stations.get(station_code)
            if station_info:
                name = station_info.name

        return name or f"station {station_code}"
