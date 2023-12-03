"""Coordinator for requesting data from the Sunsynk API."""
import asyncio
from datetime import timedelta
import logging
from typing import Any

from sunsynk.client import InvalidCredentialsException, SunsynkClient

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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


class SunsynkCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator for Sunsynk API."""

    def __init__(self, hass: HomeAssistant, api: SunsynkClient) -> None:
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

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        data: dict[str, dict[str, Any]] = {}
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with asyncio.timeout(10):
                inverters = await self.api.get_inverters()
                for inverter in inverters:
                    grid = await self.api.get_inverter_realtime_grid(inverter.sn)
                    battery = await self.api.get_inverter_realtime_battery(inverter.sn)
                    solar_pv = await self.api.get_inverter_realtime_input(inverter.sn)
                    inverter_data: dict[str, Any] = {}
                    inverter_data[BATTERY_POWER] = battery.power
                    inverter_data[BATTERY_SOC] = battery.soc
                    inverter_data[GRID_ENERGY_EXPORT_TODAY] = grid.today_export
                    inverter_data[GRID_ENERGY_EXPORT_TOTAL] = grid.total_export
                    inverter_data[GRID_ENERGY_IMPORT_TODAY] = grid.today_import
                    inverter_data[GRID_ENERGY_IMPORT_TOTAL] = grid.total_import
                    inverter_data[GRID_POWER] = grid.get_power()
                    inverter_data[SOLAR_ENERGY_TODAY] = solar_pv.generated_today
                    inverter_data[SOLAR_ENERGY_TOTAL] = solar_pv.generated_total
                    inverter_data[SOLAR_POWER] = solar_pv.get_power()
                    data[inverter.sn] = inverter_data
                return data
        except InvalidCredentialsException as err:
            raise ConfigEntryAuthFailed(err) from err
