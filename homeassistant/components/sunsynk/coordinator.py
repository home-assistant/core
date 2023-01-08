"""Coordinator for requesting data from the Sunsynk API."""
from datetime import timedelta
import logging

import async_timeout

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class SunsynkCoordinator(DataUpdateCoordinator):
    """Coordinator for Sunsynk API."""

    def __init__(self, hass, api):
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

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        inverter_sn = self.config_entry.data["inverter_sn"]
        data = {}
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                print("SunsynkCoordinator update called!")
                grid = await self.api.get_inverter_realtime_grid(inverter_sn)
                battery = await self.api.get_inverter_realtime_battery(inverter_sn)
                solar_pv = await self.api.get_inverter_realtime_input(inverter_sn)
                data["grid_energy"] = grid.get_power()
                data["battery_energy"] = battery.power
                data["solar_energy"] = solar_pv.get_power()
                return data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
