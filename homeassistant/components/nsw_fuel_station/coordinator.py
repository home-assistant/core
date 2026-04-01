"""Coordinator for the NSW Fuel Station integration."""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import logging

from nsw_fuel import FuelCheckClient, FuelCheckError, Station

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(hours=1)


@dataclass
class StationPriceData:
    """Data structure for O(1) price and name lookups."""

    stations: dict[int, Station]
    prices: dict[tuple[int, str], float]


class NSWFuelStationCoordinator(DataUpdateCoordinator[StationPriceData]):
    """Class to manage fetching NSW fuel station data."""

    config_entry: None

    def __init__(self, hass: HomeAssistant, client: FuelCheckClient) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=None,
            name="sensor",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> StationPriceData:
        """Fetch data from API."""
        return await self.hass.async_add_executor_job(
            _fetch_station_price_data, self.client
        )


def _fetch_station_price_data(client: FuelCheckClient) -> StationPriceData:
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
        raise UpdateFailed(
            f"Failed to fetch NSW Fuel station price data: {exc}"
        ) from exc
