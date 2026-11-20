"""Coordinator for the Buienradar integration."""

from datetime import timedelta
import logging
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_TIMEFRAME, DEFAULT_TIMEFRAME, DOMAIN, SCHEDULE_NOK, SCHEDULE_OK
from .util import BuienradarData, async_fetch_data, async_in_service_quiet_hour

_LOGGER = logging.getLogger(__name__)

type BuienRadarConfigEntry = ConfigEntry[BuienradarCoordinator]


class BuienradarCoordinator(DataUpdateCoordinator[BuienradarData]):
    """Fetch the Buienradar weather data for the configured location."""

    config_entry: BuienRadarConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: BuienRadarConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=SCHEDULE_OK),
        )
        config = config_entry.data
        self.coordinates = {
            CONF_LATITUDE: float(config.get(CONF_LATITUDE, hass.config.latitude)),
            CONF_LONGITUDE: float(config.get(CONF_LONGITUDE, hass.config.longitude)),
        }
        timeframe = config_entry.options.get(
            CONF_TIMEFRAME, config.get(CONF_TIMEFRAME, DEFAULT_TIMEFRAME)
        )
        self._timeframe = timeframe

    @override
    async def _async_update_data(self) -> BuienradarData:
        """Fetch the latest data from Buienradar."""
        try:
            data = await async_fetch_data(self.hass, self.coordinates, self._timeframe)
        except UpdateFailed:
            self.update_interval = timedelta(minutes=SCHEDULE_NOK)
            if (
                previous := self.data_or_none
            ) is not None and await async_in_service_quiet_hour():
                # Keep the last data while the service updates its forecast
                return previous
            raise
        self.update_interval = timedelta(minutes=SCHEDULE_OK)
        return BuienradarData(data)
