"""SAJ data update coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging

import pysaj

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MIN_INTERVAL_SEC = 5
MAX_INTERVAL_SEC = 300


class SAJDataUpdateCoordinator(DataUpdateCoordinator[bool]):
    """Fetch SAJ inverter sensor data with backoff when reads fail."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        saj: pysaj.SAJ,
        sensor_def: pysaj.Sensors,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=MIN_INTERVAL_SEC),
        )
        self._saj = saj
        self.sensor_def = sensor_def
        self._fail_interval_sec = MIN_INTERVAL_SEC

    async def _async_update_data(self) -> bool:
        """Read sensors from the inverter."""
        try:
            success = await self._saj.read(self.sensor_def)
        except pysaj.UnauthorizedException as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except pysaj.UnexpectedResponseException as err:
            _LOGGER.error(
                "Error in SAJ, please check host/ip address. Original error: %s", err
            )
            success = False
        except (TimeoutError, OSError) as err:
            _LOGGER.error("Error communicating with SAJ: %s", err)
            success = False

        if success:
            self._fail_interval_sec = MIN_INTERVAL_SEC
            self.update_interval = timedelta(seconds=MIN_INTERVAL_SEC)
        else:
            self._fail_interval_sec = min(self._fail_interval_sec * 2, MAX_INTERVAL_SEC)
            self.update_interval = timedelta(seconds=self._fail_interval_sec)

        return success
