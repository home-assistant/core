"""The nsw_fuel_station component."""
from __future__ import annotations

from dataclasses import dataclass
import datetime
import logging

from nsw_fuel import FuelCheckClient, FuelCheckError, Station

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_NSW_FUEL_STATION

_LOGGER = logging.getLogger(__name__)

DOMAIN = "nsw_fuel_station"
SCAN_INTERVAL = datetime.timedelta(hours=1)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
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

    stations: dict[int, Station]
    prices: dict[tuple[int, str], float]


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
        raise UpdateFailed(
            f"Failed to fetch NSW Fuel station price data: {exc}"
        ) from exc
