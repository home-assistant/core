"""The nsw_fuel_station component."""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Tuple, Dict

from nsw_fuel import FuelCheckClient, FuelCheckError, Station

from homeassistant.components.nsw_fuel_station.const import DATA_NSW_FUEL_STATION
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

DOMAIN = "nsw_fuel_station"
SCAN_INTERVAL = datetime.timedelta(hours=1)


async def async_setup(hass, config):
    """Set up the NSW Fuel Station platform."""
    client = FuelCheckClient()

    async def async_update_data():
        return await hass.async_add_executor_job(fetch_station_price_data, client)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_interval=SCAN_INTERVAL,
        update_method=async_update_data,
    )
    hass.data[DATA_NSW_FUEL_STATION] = coordinator

    await coordinator.async_refresh()

    return True


@dataclass
class StationPriceData:
    """Data structure for O(1) price and name lookups."""

    stations: Dict[int, Station]
    prices: Dict[Tuple[int, str], float]


def fetch_station_price_data(client: FuelCheckClient) -> StationPriceData | None:
    """Fetch fuel price and station data."""
    try:
        raw_price_data = client.get_fuel_prices()
        # Restructure prices and station details to be indexed by station code
        # for O(1) lookup
        return StationPriceData(
            stations={s.code: s for s in raw_price_data.stations},
            prices={
                (p.station_code, p.fuel_type): p.price for p in raw_price_data.prices
            },
        )

    except FuelCheckError as exc:
        _LOGGER.error("Failed to fetch NSW Fuel station price data. %s", exc)
        return None
