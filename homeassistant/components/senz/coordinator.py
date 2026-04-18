"""Data update coordinator for SENZ."""

from __future__ import annotations

from datetime import timedelta
import logging

from httpx import RequestError
from pysenz import SENZAPI, Thermostat

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

UPDATE_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)

type SENZConfigEntry = ConfigEntry[SENZDataUpdateCoordinator]


class SENZDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Thermostat]]):
    """Class to manage fetching SENZ data."""

    config_entry: SENZConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SENZConfigEntry,
        *,
        name: str,
        senz_api: SENZAPI,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=name,
            update_interval=UPDATE_INTERVAL,
        )
        self._senz_api = senz_api

    async def _async_update_data(self) -> dict[str, Thermostat]:
        """Fetch data from SENZ."""
        try:
            thermostats = await self._senz_api.get_thermostats()
        except RequestError as err:
            raise UpdateFailed from err
        return {thermostat.serial_number: thermostat for thermostat in thermostats}
