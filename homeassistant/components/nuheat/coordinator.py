"""DataUpdateCoordinator for NuHeat thermostats."""

from datetime import timedelta
import logging

import nuheat

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_SERIAL_NUMBER

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)


class NuHeatCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for NuHeat thermostat data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        thermostat: nuheat.NuHeatThermostat,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"nuheat {entry.data[CONF_SERIAL_NUMBER]}",
            update_interval=SCAN_INTERVAL,
        )
        self.thermostat = thermostat

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        await self.hass.async_add_executor_job(self.thermostat.get_data)
