"""Data coordinator for nsw_fuel."""

from dataclasses import dataclass
from datetime import timedelta
import logging

from nsw_fuel import FuelCheckClient, Station

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type NswFuelStationConfigEntry = ConfigEntry[NswFuelStationDataUpdateCoordinator]


@dataclass
class NswFuelStationCoordinatorData:
    """Data class for storing coordinator data."""

    stations: dict[int, Station]
    prices: dict[tuple[int, str], float]
    fuel_types: dict[str, str]


class NswFuelStationDataUpdateCoordinator(
    DataUpdateCoordinator[NswFuelStationCoordinatorData]
):
    """Coordinator for Nsw Fuel data."""

    client: FuelCheckClient
    config_entry: NswFuelStationConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialise the data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=1),
        )
        self.client = FuelCheckClient()

    async def _async_update_data(self) -> NswFuelStationCoordinatorData:
        """Fetch updated data."""
        price_data = NswFuelStationCoordinatorData(
            stations={},
            prices={},
            fuel_types={},
        )
        raw_price_data = await self.hass.async_add_executor_job(
            self.client.get_fuel_prices
        )
        if self.data is None or len(self.data.fuel_types) < 1:
            reference_data = await self.hass.async_add_executor_job(
                self.client.get_reference_data
            )
            price_data.fuel_types = {f.code: f.name for f in reference_data.fuel_types}
        else:
            price_data.fuel_types = self.data.fuel_types

        # Restructure prices and station details to be indexed by station code
        # for O(1) lookup
        price_data.stations = {s.code: s for s in raw_price_data.stations}
        price_data.prices = {
            (p.station_code, p.fuel_type): p.price for p in raw_price_data.prices
        }

        return price_data
