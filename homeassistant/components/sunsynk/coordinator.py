"""Coordinator for requesting data from the Sunsynk API."""
from datetime import timedelta
import logging
from typing import Any

import async_timeout
from sunsynk.client import InvalidCredentialsException, SunsynkClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    BATTERY_POWER,
    BATTERY_SOC,
    GRID_ENERGY_EXPORT_TODAY,
    GRID_ENERGY_EXPORT_TOTAL,
    GRID_ENERGY_IMPORT_TODAY,
    GRID_ENERGY_IMPORT_TOTAL,
    GRID_POWER,
    SOLAR_ENERGY_TODAY,
    SOLAR_ENERGY_TOTAL,
    SOLAR_POWER,
)

_LOGGER = logging.getLogger(__name__)


class SunsynkCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Sunsynk API."""

    def __init__(
        self, hass: HomeAssistant, api: SunsynkClient, inverter_sn: str
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Sunsynk",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(minutes=2),
        )
        self.api = api
        self.inverter_sn = inverter_sn

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        data: dict[str, Any] = {}
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                grid = await self.api.get_inverter_realtime_grid(self.inverter_sn)
                battery = await self.api.get_inverter_realtime_battery(self.inverter_sn)
                solar_pv = await self.api.get_inverter_realtime_input(self.inverter_sn)
                data[BATTERY_POWER] = battery.power
                data[BATTERY_SOC] = battery.soc
                data[GRID_ENERGY_EXPORT_TODAY] = grid.today_export
                data[GRID_ENERGY_EXPORT_TOTAL] = grid.total_export
                data[GRID_ENERGY_IMPORT_TODAY] = grid.today_import
                data[GRID_ENERGY_IMPORT_TOTAL] = grid.total_import
                data[GRID_POWER] = grid.get_power()
                data[SOLAR_ENERGY_TODAY] = solar_pv.generated_today
                data[SOLAR_ENERGY_TOTAL] = solar_pv.generated_total
                data[SOLAR_POWER] = solar_pv.get_power()
                return data
        except InvalidCredentialsException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
