"""The nsw_fuel_station component."""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import logging
from typing import TYPE_CHECKING

import nsw_fuel

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(hours=1)

CONFIG_SCHEMA = cv.platform_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    client = nsw_fuel.FuelCheckClient()

    async def async_update_data():
        return await hass.async_add_executor_job(fetch_station_price_data, client)

    if hass.data.get(DOMAIN) is None:
        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            config_entry=entry,
            name="sensor",
            update_interval=SCAN_INTERVAL,
            update_method=async_update_data,
        )
        hass.data[DOMAIN] = coordinator

        await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


@dataclass
class StationPriceData:
    """Data structure for O(1) price and name lookups."""

    stations: dict[int, nsw_fuel.Station]
    prices: dict[int, dict[str, float]]
    fuel_types: dict[str, str]


def fetch_station_price_data(
    client: nsw_fuel.FuelCheckClient,
) -> StationPriceData | None:
    """Fetch fuel price and station data."""
    try:
        raw_price_data = client.get_fuel_prices()
        reference_data = client.get_reference_data()
        # Restructure prices and station details to be indexed by station code
        # for O(1) lookup
        prices: dict[int, dict[str, float]] = {}
        for p in raw_price_data.prices:
            station_prices = prices.setdefault(p.station_code, {})
            station_prices[p.fuel_type] = p.price
            prices[p.station_code] = station_prices
        return StationPriceData(
            stations={s.code: s for s in raw_price_data.stations},
            prices=prices,
            fuel_types={f.code: f.name for f in reference_data.fuel_types},
        )

    except nsw_fuel.FuelCheckError as exc:
        raise UpdateFailed(
            f"Failed to fetch NSW Fuel station price data: {exc}"
        ) from exc
