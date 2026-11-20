"""DataUpdateCoordinator for the IRM KMI integration."""

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Final, override

from irm_kmi_api import IrmKmiApiClientHa, IrmKmiApiError, PollenLevel, PollenName

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .data import ProcessedCoordinatorData
from .utils import preferred_language

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL: Final = timedelta(minutes=7)
GRACE_PERIOD: Final = 2.5 * UPDATE_INTERVAL

type IrmKmiConfigEntry = ConfigEntry[IrmKmiRuntimeData]


@dataclass
class IrmKmiRuntimeData:
    """Coordinators of an IRM KMI config entry."""

    weather: IrmKmiCoordinator
    pollen: IrmKmiPollenCoordinator


class IrmKmiCoordinator(TimestampDataUpdateCoordinator[ProcessedCoordinatorData]):
    """Coordinator to update data from IRM KMI."""

    config_entry: IrmKmiConfigEntry

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
                    "lat": self._location[CONF_LATITUDE],
                    "long": self._location[CONF_LONGITUDE],
                }
            )

        except IrmKmiApiError as err:
            if self._within_grace(self._last_api_success_time):
                return self.data
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"error": str(err)},
            ) from err

        data = await self.process_api_data()
        # Only once processed, so the grace period never serves missing data
        self._last_api_success_time = dt_util.utcnow()
        return data

    async def process_api_data(self) -> ProcessedCoordinatorData:
        """From the API data, create the object that will be used in the entities."""
        tz = await dt_util.async_get_time_zone("Europe/Brussels")
        if TYPE_CHECKING:
            assert tz is not None
        lang = preferred_language(self.hass, self.config_entry)

        return ProcessedCoordinatorData(
            current_weather=self._api.get_current_weather(tz),
            daily_forecast=self._api.get_daily_forecast(tz, lang),
            hourly_forecast=self._api.get_hourly_forecast(tz),
            country=self._api.get_country(),
            warnings=self._api.get_warnings(lang),
        )


class IrmKmiPollenCoordinator(
    DataUpdateCoordinator[dict[PollenName, PollenLevel | None]]
):
    """Coordinator to update the pollen levels from IRM KMI.

    The pollen image is linked from the forecast, so this relies on the forecast
    the weather coordinator refreshed on the shared API client.
    """

    config_entry: IrmKmiConfigEntry

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
            name="IRM KMI pollen",
            update_interval=UPDATE_INTERVAL,
        )
        self._api = api_client

    @override
    async def _async_update_data(self) -> dict[PollenName, PollenLevel | None]:
        """Fetch the pollen levels."""
        try:
            return await self._api.get_pollen()
        except IrmKmiApiError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"error": str(err)},
            ) from err
