"""DataUpdateCoordinator for the IRM KMI integration."""

from datetime import datetime, timedelta
import logging

from irm_kmi_api import IrmKmiApiClientHa, IrmKmiApiError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_LOCATION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.dt import utcnow

from .data import ProcessedCoordinatorData
from .utils import preferred_language

GRACE_FACTOR = 2.5

_LOGGER = logging.getLogger(__name__)

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
            update_interval=timedelta(minutes=7),
        )
        self._api = api_client
        self._location = entry.data[CONF_LOCATION]
        # We have to track the last successful update separately from the coordinator's built-in last_update_success,
        # because _async_update_data can return old data without raising an exception, which still counts as a
        # successful update for the coordinator.
        self._last_successful_api_update: datetime | None = None
        self._api_reachable: bool | None = None

    async def _async_update_data(self) -> ProcessedCoordinatorData:
        """Fetch data from API endpoint.

        Pre-process the data to lookup tables so entities
        can quickly look up their data.
        """

        self._api.expire_cache()

        try:
            await self._api.refresh_forecasts_coord(
                {
                    "lat": self._location[ATTR_LATITUDE],
                    "long": self._location[ATTR_LONGITUDE],
                }
            )

        except IrmKmiApiError as err:
            self._api_reachable = False

            if (
                self.data is not None
                and self._last_successful_api_update is not None
                and self.update_interval is not None
                and utcnow() - self._last_successful_api_update
                < GRACE_FACTOR * self.update_interval
            ):
                return self.data

            success_info = (
                f"Last success time is: {self._last_successful_api_update.isoformat()}"
                if self._last_successful_api_update is not None
                else "No successful API update yet."
            )
            raise UpdateFailed(
                f"Error communicating with API for general forecast: {err}. {success_info}"
            ) from err

        data = await self.process_api_data()
        self._last_successful_api_update = utcnow()

        if self._api_reachable is False:
            _LOGGER.warning("Successfully reconnected to the API")
        self._api_reachable = True

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
