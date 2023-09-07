"""DataUpdateCoordinator for the srp_energy integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta

from srpenergy.client import SrpEnergyClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER, MIN_TIME_BETWEEN_UPDATES, PHOENIX_TIME_ZONE

TIMEOUT = 10


class SRPEnergyDataUpdateCoordinator(DataUpdateCoordinator[float]):
    """A srp_energy Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, client: SrpEnergyClient, is_time_of_use: bool
    ) -> None:
        """Initialize the srp_energy data coordinator."""
        self._client = client
        self._is_time_of_use = is_time_of_use
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )

    async def _async_update_data(self) -> float:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        LOGGER.debug("async_update_data enter")
        # Fetch srp_energy data
        phx_time_zone = dt_util.get_time_zone(PHOENIX_TIME_ZONE)
        end_date = dt_util.now(phx_time_zone)
        start_date = end_date - timedelta(days=1)
        try:
            async with asyncio.timeout(TIMEOUT):
                hourly_usage = await self.hass.async_add_executor_job(
                    self._client.usage,
                    start_date,
                    end_date,
                    self._is_time_of_use,
                )
        except (ValueError, TypeError) as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        LOGGER.debug(
            "async_update_data: Received %s record(s) from %s to %s",
            len(hourly_usage) if hourly_usage else "None",
            start_date,
            end_date,
        )

        previous_daily_usage = 0.0
        for _, _, _, kwh, _ in hourly_usage:
            previous_daily_usage += float(kwh)

        LOGGER.debug(
            "async_update_data: previous_daily_usage %s",
            previous_daily_usage,
        )

        return previous_daily_usage
