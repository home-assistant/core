"""The nsw_fuel_station component."""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import logging
from typing import TYPE_CHECKING

from nsw_fuel import FuelCheckClient, FuelCheckError, Station

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

from .const import DATA_NSW_FUEL_STATION

DOMAIN = "nsw_fuel_station"
SCAN_INTERVAL = datetime.timedelta(hours=1)

CONFIG_SCHEMA = cv.platform_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the NSW Fuel Station platform."""
    client = FuelCheckClient()

    async def async_update_data() -> StationPriceData:
        return await hass.async_add_executor_job(fetch_station_price_data, hass, client)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=None,
        name="sensor",
        update_interval=SCAN_INTERVAL,
        update_method=async_update_data,
    )
    hass.data[DATA_NSW_FUEL_STATION] = coordinator

    await coordinator.async_refresh()

    if "sensor" not in config:
        return True

    for platform_config in config["sensor"]:
        if platform_config["platform"] == "nsw_fuel_station":
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data=dict(platform_config),  # Convert to dict
                )
            )

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up this integration using UI."""
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

    stations: dict[int, Station]
    prices: dict[tuple[int, str], float]
    fuel_types: dict[str, str]


def fetch_station_price_data(
    hass: HomeAssistant, client: FuelCheckClient
) -> StationPriceData:
    """Fetch fuel price and station data."""
    try:
        raw_price_data = client.get_fuel_prices()
        reference_data = client.get_reference_data()
    except FuelCheckError as exc:
        raise UpdateFailed(
            f"Failed to fetch NSW Fuel station price data: {exc}"
        ) from exc

    # Restructure prices and station details to be indexed by station code
    # for O(1) lookup
    price_data = StationPriceData(
        stations={s.code: s for s in raw_price_data.stations},
        prices={(p.station_code, p.fuel_type): p.price for p in raw_price_data.prices},
        fuel_types={},
    )

    price_data.fuel_types = {f.code: f.name for f in reference_data.fuel_types}

    return price_data
