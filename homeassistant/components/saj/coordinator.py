"""DataUpdateCoordinator for the SAJ Solar Inverter integration."""

from datetime import timedelta
import logging
from typing import override

import pysaj

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

type SAJConfigEntry = ConfigEntry[SAJDataUpdateCoordinator]


class SAJDataUpdateCoordinator(DataUpdateCoordinator[pysaj.Sensors]):
    """Coordinator to poll a SAJ inverter and share data with all sensors."""

    config_entry: SAJConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SAJConfigEntry,
        saj: pysaj.SAJ,
        sensor_def: pysaj.Sensors,
        *,
        wifi: bool,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.saj = saj
        self.sensor_def = sensor_def
        self._wifi = wifi

    @override
    async def _async_update_data(self) -> pysaj.Sensors:
        """Fetch the latest data from the inverter."""
        try:
            success = await self.saj.read(self.sensor_def)
        except pysaj.UnauthorizedException as err:
            # On ethernet an unauthorized response usually means a wrong
            # connection type, which is a recoverable connection problem.
            if self._wifi:
                raise ConfigEntryAuthFailed("Authentication failed") from err
            raise UpdateFailed("Wrong connection type or cannot connect") from err
        except (pysaj.UnexpectedResponseException, TimeoutError, OSError) as err:
            raise UpdateFailed(f"Error communicating with the inverter: {err}") from err

        if not success:
            raise UpdateFailed("Failed to read sensor data from the inverter")

        return self.sensor_def
