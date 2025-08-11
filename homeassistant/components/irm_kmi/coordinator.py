"""DataUpdateCoordinator for the IRM KMI integration."""

from datetime import timedelta
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
        self._location = entry.data.get(CONF_LOCATION)

    async def _async_update_data(self) -> ProcessedCoordinatorData:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables so entities can quickly look up their data.
        :return: ProcessedCoordinatorData
        """

        self._api.expire_cache()

        # Condition is needed to avoid mypy error about Any | None type having no attribute get or non-indexable value
        if (
            self._location is None
            or self._location.get(ATTR_LATITUDE) is None
            or self._location.get(ATTR_LONGITUDE) is None
        ):
            raise UpdateFailed(
                "Unknown value for either latitude or longitude in the configuration"
            )

        try:
            await self._api.refresh_forecasts_coord(
                {
                    "lat": self._location.get(ATTR_LATITUDE),
                    "long": self._location.get(ATTR_LONGITUDE),
                }
            )

        except IrmKmiApiError as err:
            if (
                self.last_update_success_time is not None
                and self.update_interval is not None
                and self.last_update_success_time - utcnow()
                < timedelta(seconds=2.5 * self.update_interval.seconds)
            ):
                _LOGGER.warning(
                    "Error communicating with API for general forecast: %s. Keeping the old data",
                    err,
                )
                return self.data
            raise UpdateFailed(
                f"Error communicating with API for general forecast: {err}. "
                f"Last success time is: {self.last_update_success_time}"
            ) from err

        return await self.process_api_data()

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
