"""Zeversolar coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging

import zeversolar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Suppress noisy retry logs from zeversolar library during offline periods
logging.getLogger("retry.api").setLevel(logging.ERROR)


class ZeversolarCoordinator(DataUpdateCoordinator[zeversolar.ZeverSolarData | None]):
    """Data update coordinator."""

    config_entry: ConfigEntry
    is_online: bool = False
    last_known_data: zeversolar.ZeverSolarData | None = None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )
        self._client = zeversolar.ZeverSolarClient(host=entry.data[CONF_HOST])

    async def _async_update_data(self) -> zeversolar.ZeverSolarData | None:
        """Fetch the latest data from the source."""
        try:
            data = await self.hass.async_add_executor_job(self._client.get_data)
            if data:
                self.is_online = True
                self.last_known_data = data
                _LOGGER.debug("Successfully retrieved data from Zeversolar inverter")
                return data
            else:
                # No data received, inverter might be offline (night time/no sun)
                self.is_online = False
                _LOGGER.debug("No data received from Zeversolar inverter - likely offline (night time)")
                return None
        except Exception as err:
            # Connection error - inverter is offline (normal behavior at night)
            self.is_online = False
            
            # Always treat as normal offline behavior, no error logging
            # This prevents error notifications in HA when inverter is naturally offline
            _LOGGER.debug("Zeversolar inverter is offline (normal night/low sun behavior): %s", type(err).__name__)
            
            # Return None instead of raising exception to prevent HA from showing errors
            return None
