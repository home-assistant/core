"""DataUpdateCoordinator for the MeteoAlarm integration."""

from datetime import timedelta
import logging
from typing import Any, override

from meteoalarmapi import Meteoalert, ServerError, UnexpectedError, WrongCountry

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)

type MeteoAlarmConfigEntry = ConfigEntry[MeteoAlarmCoordinator]


class MeteoAlarmCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch the most severe alert for a region from MeteoAlarm."""

    config_entry: MeteoAlarmConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MeteoAlarmConfigEntry,
        api: Meteoalert,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the most severe alert, or an empty dict when there is none."""
        try:
            return await self.hass.async_add_executor_job(self.api.get_alert)
        except (ServerError, UnexpectedError, WrongCountry) as err:
            raise UpdateFailed(f"Error fetching MeteoAlarm data: {err}") from err
