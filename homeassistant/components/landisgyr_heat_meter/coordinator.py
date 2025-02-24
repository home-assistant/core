"""Data update coordinator for the ultraheat api."""

import asyncio
import logging

import serial
from ultraheat_api.response import HeatMeterResponse
from ultraheat_api.service import HeatMeterService

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import POLLING_INTERVAL, ULTRAHEAT_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class UltraheatCoordinator(DataUpdateCoordinator[HeatMeterResponse]):
    """Coordinator for getting data from the ultraheat api."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: HeatMeterService
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="ultraheat",
            update_interval=POLLING_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> HeatMeterResponse:
        """Fetch data from API endpoint."""
        try:
            async with asyncio.timeout(ULTRAHEAT_TIMEOUT):
                return await self.hass.async_add_executor_job(self.api.read)
        except (FileNotFoundError, serial.SerialException) as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
