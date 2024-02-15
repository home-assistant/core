"""DataUpdateCoordinator for the AirNow integration."""
from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectorError
from pyairnow import WebServiceAPI
from pyairnow.conv import aqi_to_concentration
from pyairnow.errors import AirNowError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_API_AQI,
    ATTR_API_AQI_DESCRIPTION,
    ATTR_API_AQI_LEVEL,
    ATTR_API_AQI_PARAM,
    ATTR_API_CAT_DESCRIPTION,
    ATTR_API_CAT_LEVEL,
    ATTR_API_CATEGORY,
    ATTR_API_PM25,
    ATTR_API_POLLUTANT,
    ATTR_API_REPORT_DATE,
    ATTR_API_REPORT_HOUR,
    ATTR_API_REPORT_TZ,
    ATTR_API_STATE,
    ATTR_API_STATION,
    ATTR_API_STATION_LATITUDE,
    ATTR_API_STATION_LONGITUDE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class AirNowDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """The AirNow update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
        api_key: str,
        latitude: float,
        longitude: float,
        distance: int,
        update_interval: timedelta,
    ) -> None:
        """Initialize."""
        self.latitude = latitude
        self.longitude = longitude
        self.distance = distance

        self.airnow = WebServiceAPI(api_key, session=session)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        data = {}
        try:
            obs = await self.airnow.observations.latLong(
                self.latitude,
                self.longitude,
                distance=self.distance,
            )

        except (AirNowError, ClientConnectorError) as error:
            raise UpdateFailed(error) from error

        if not obs:
            raise UpdateFailed("No data was returned from AirNow")

        max_aqi = 0
        max_aqi_level = 0
        max_aqi_desc = ""
        max_aqi_poll = ""
        for obv in obs:
            # Convert AQIs to Concentration
            pollutant = obv[ATTR_API_AQI_PARAM]
            concentration = aqi_to_concentration(obv[ATTR_API_AQI], pollutant)
            data[obv[ATTR_API_AQI_PARAM]] = concentration

            # Overall AQI is the max of all pollutant AQIs
            if obv[ATTR_API_AQI] > max_aqi:
                max_aqi = obv[ATTR_API_AQI]
                max_aqi_level = obv[ATTR_API_CATEGORY][ATTR_API_CAT_LEVEL]
                max_aqi_desc = obv[ATTR_API_CATEGORY][ATTR_API_CAT_DESCRIPTION]
                max_aqi_poll = pollutant

            # Copy other data from PM2.5 Value
            if obv[ATTR_API_AQI_PARAM] == ATTR_API_PM25:
                # Copy Report Details
                data[ATTR_API_REPORT_DATE] = obv[ATTR_API_REPORT_DATE]
                data[ATTR_API_REPORT_HOUR] = obv[ATTR_API_REPORT_HOUR]
                data[ATTR_API_REPORT_TZ] = obv[ATTR_API_REPORT_TZ]

                # Copy Station Details
                data[ATTR_API_STATE] = obv[ATTR_API_STATE]
                data[ATTR_API_STATION] = obv[ATTR_API_STATION]
                data[ATTR_API_STATION_LATITUDE] = obv[ATTR_API_STATION_LATITUDE]
                data[ATTR_API_STATION_LONGITUDE] = obv[ATTR_API_STATION_LONGITUDE]

        # Store Overall AQI
        data[ATTR_API_AQI] = max_aqi
        data[ATTR_API_AQI_LEVEL] = max_aqi_level
        data[ATTR_API_AQI_DESCRIPTION] = max_aqi_desc
        data[ATTR_API_POLLUTANT] = max_aqi_poll

        return data
