"""DataUpdateCoordinator for the IRM KMI integration."""

from datetime import datetime, timedelta
import logging
from typing import Final, override

from irm_kmi_api import IrmKmiApiClientHa, IrmKmiApiError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_LOCATION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .data import ProcessedCoordinatorData
from .utils import preferred_language

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL: Final = timedelta(minutes=7)
GRACE_PERIOD: Final = 2.5 * UPDATE_INTERVAL

type IrmKmiConfigEntry = ConfigEntry[IrmKmiCoordinator]


class IrmKmiCoordinator(TimestampDataUpdateCoordinator[ProcessedCoordinatorData]):
    """Coordinator to update data from IRM KMI."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: IrmKmiConfigEntry,
        api_client: IrmKmiApiClientHa,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="IRM KMI weather",
            update_interval=UPDATE_INTERVAL,
        )
        self._api = api_client
        self._location = entry.data[CONF_LOCATION]
        # last_update_success_time is also renewed while serving old data
        self._last_api_success_time: datetime | None = None

    def _within_grace(self, last_success: datetime | None) -> bool:
        """Return whether data from the last success may still be served."""
        return (
            last_success is not None and dt_util.utcnow() - last_success < GRACE_PERIOD
        )

    @override
    async def _async_update_data(self) -> ProcessedCoordinatorData:
        """Fetch and process the IRM KMI data."""
        self._api.expire_cache()

        try:
            await self._api.refresh_forecasts_coord(
                {
                    "lat": self._location[ATTR_LATITUDE],
                    "long": self._location[ATTR_LONGITUDE],
                }
            )

        except IrmKmiApiError as err:
            if self._within_grace(self._last_api_success_time):
                return self.data
            raise UpdateFailed(
                f"Error communicating with API for general forecast: {err}. "
                f"Last success time is: {self._last_api_success_time}"
            ) from err

        data = await self.process_api_data()
        # Only once processed, so the grace period never serves missing data
        self._last_api_success_time = dt_util.utcnow()
        return data

    async def process_api_data(self) -> ProcessedCoordinatorData:
        """From the API data, create the object that will be used in the entities."""
        tz = await dt_util.async_get_time_zone("Europe/Brussels")
        lang = preferred_language(self.hass, self.config_entry)

        return ProcessedCoordinatorData(
            current_weather=self._api.get_current_weather(tz),
            daily_forecast=self._api.get_daily_forecast(tz, lang),
            hourly_forecast=self._api.get_hourly_forecast(tz),
            country=self._api.get_country(),
        )
