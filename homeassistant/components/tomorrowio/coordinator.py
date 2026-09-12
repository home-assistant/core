"""The Tomorrow.io integration."""

from datetime import timedelta
from math import ceil
from typing import Any, override

from pytomorrowio import TomorrowioV4
from pytomorrowio.exceptions import (
    CantConnectException,
    InvalidAPIKeyException,
    RateLimitedException,
    UnknownException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_TIMESTEP,
    DOMAIN,
    LOGGER,
    SUBENTRY_TYPE_LOCATION,
    TMRW_ATTR_CARBON_MONOXIDE,
    TMRW_ATTR_CHINA_AQI,
    TMRW_ATTR_CHINA_HEALTH_CONCERN,
    TMRW_ATTR_CHINA_PRIMARY_POLLUTANT,
    TMRW_ATTR_CLOUD_BASE,
    TMRW_ATTR_CLOUD_CEILING,
    TMRW_ATTR_CLOUD_COVER,
    TMRW_ATTR_CONDITION,
    TMRW_ATTR_DEW_POINT,
    TMRW_ATTR_EPA_AQI,
    TMRW_ATTR_EPA_HEALTH_CONCERN,
    TMRW_ATTR_EPA_PRIMARY_POLLUTANT,
    TMRW_ATTR_FEELS_LIKE,
    TMRW_ATTR_FIRE_INDEX,
    TMRW_ATTR_HUMIDITY,
    TMRW_ATTR_NITROGEN_DIOXIDE,
    TMRW_ATTR_OZONE,
    TMRW_ATTR_PARTICULATE_MATTER_10,
    TMRW_ATTR_PARTICULATE_MATTER_25,
    TMRW_ATTR_POLLEN_GRASS,
    TMRW_ATTR_POLLEN_TREE,
    TMRW_ATTR_POLLEN_WEED,
    TMRW_ATTR_PRECIPITATION,
    TMRW_ATTR_PRECIPITATION_PROBABILITY,
    TMRW_ATTR_PRECIPITATION_TYPE,
    TMRW_ATTR_PRESSURE,
    TMRW_ATTR_PRESSURE_SURFACE_LEVEL,
    TMRW_ATTR_SOLAR_GHI,
    TMRW_ATTR_SULPHUR_DIOXIDE,
    TMRW_ATTR_TEMPERATURE,
    TMRW_ATTR_TEMPERATURE_HIGH,
    TMRW_ATTR_TEMPERATURE_LOW,
    TMRW_ATTR_UV_HEALTH_CONCERN,
    TMRW_ATTR_UV_INDEX,
    TMRW_ATTR_VISIBILITY,
    TMRW_ATTR_WIND_DIRECTION,
    TMRW_ATTR_WIND_GUST,
    TMRW_ATTR_WIND_SPEED,
)

type TomorrowioConfigEntry = ConfigEntry[TomorrowioDataUpdateCoordinator]


def calculate_update_interval(
    num_locations: int, num_api_requests: int, max_requests_per_day: int
) -> timedelta:
    """Calculate update_interval.

    Calculate the interval to not exceed the allowed number of requests for all
    configured locations. Divide 90% of max_requests by the number of API calls
    because we want a buffer in the number of API calls left at the end of the
    day.
    """
    minutes = ceil(
        (24 * 60 * num_locations * num_api_requests) / (max_requests_per_day * 0.9)
    )
    LOGGER.debug(
        (
            "Number of locations: %s\n"
            "Number of API Requests per call: %s\n"
            "Max requests per day: %s\n"
            "Update interval: %s minutes"
        ),
        num_locations,
        num_api_requests,
        max_requests_per_day,
        minutes,
    )
    return timedelta(minutes=minutes)


class TomorrowioDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Define an object to hold Tomorrow.io data."""

    config_entry: TomorrowioConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TomorrowioConfigEntry,
        api: TomorrowioV4,
    ) -> None:
        """Initialize."""
        self._api = api
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{api.api_key_masked}",
            update_interval=calculate_update_interval(
                len(config_entry.get_subentries_of_type(SUBENTRY_TYPE_LOCATION)),
                api.num_api_requests,
                api.max_requests_per_day,
            ),
        )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        data: dict[str, Any] = {}
        subentries = self.config_entry.get_subentries_of_type(SUBENTRY_TYPE_LOCATION)
        LOGGER.debug("Fetching data for %s locations", len(subentries))
        for subentry in subentries:
            location = subentry.data[CONF_LOCATION]
            try:
                data[subentry.subentry_id] = await self._api.realtime_and_all_forecasts(
                    [
                        # Weather
                        TMRW_ATTR_TEMPERATURE,
                        TMRW_ATTR_HUMIDITY,
                        TMRW_ATTR_PRESSURE,
                        TMRW_ATTR_WIND_SPEED,
                        TMRW_ATTR_WIND_DIRECTION,
                        TMRW_ATTR_CONDITION,
                        TMRW_ATTR_VISIBILITY,
                        TMRW_ATTR_OZONE,
                        TMRW_ATTR_WIND_GUST,
                        TMRW_ATTR_CLOUD_COVER,
                        TMRW_ATTR_PRECIPITATION_TYPE,
                        # Sensors
                        TMRW_ATTR_CARBON_MONOXIDE,
                        TMRW_ATTR_CHINA_AQI,
                        TMRW_ATTR_CHINA_HEALTH_CONCERN,
                        TMRW_ATTR_CHINA_PRIMARY_POLLUTANT,
                        TMRW_ATTR_CLOUD_BASE,
                        TMRW_ATTR_CLOUD_CEILING,
                        TMRW_ATTR_CLOUD_COVER,
                        TMRW_ATTR_DEW_POINT,
                        TMRW_ATTR_EPA_AQI,
                        TMRW_ATTR_EPA_HEALTH_CONCERN,
                        TMRW_ATTR_EPA_PRIMARY_POLLUTANT,
                        TMRW_ATTR_FEELS_LIKE,
                        TMRW_ATTR_FIRE_INDEX,
                        TMRW_ATTR_NITROGEN_DIOXIDE,
                        TMRW_ATTR_OZONE,
                        TMRW_ATTR_PARTICULATE_MATTER_10,
                        TMRW_ATTR_PARTICULATE_MATTER_25,
                        TMRW_ATTR_POLLEN_GRASS,
                        TMRW_ATTR_POLLEN_TREE,
                        TMRW_ATTR_POLLEN_WEED,
                        TMRW_ATTR_PRECIPITATION_TYPE,
                        TMRW_ATTR_PRESSURE_SURFACE_LEVEL,
                        TMRW_ATTR_SOLAR_GHI,
                        TMRW_ATTR_SULPHUR_DIOXIDE,
                        TMRW_ATTR_UV_INDEX,
                        TMRW_ATTR_UV_HEALTH_CONCERN,
                        TMRW_ATTR_WIND_GUST,
                    ],
                    [
                        TMRW_ATTR_TEMPERATURE_LOW,
                        TMRW_ATTR_TEMPERATURE_HIGH,
                        TMRW_ATTR_DEW_POINT,
                        TMRW_ATTR_HUMIDITY,
                        TMRW_ATTR_WIND_SPEED,
                        TMRW_ATTR_WIND_DIRECTION,
                        TMRW_ATTR_CONDITION,
                        TMRW_ATTR_PRECIPITATION,
                        TMRW_ATTR_PRECIPITATION_PROBABILITY,
                    ],
                    nowcast_timestep=subentry.data[CONF_TIMESTEP],
                    location=f"{location[CONF_LATITUDE]},{location[CONF_LONGITUDE]}",
                )
            except (
                CantConnectException,
                InvalidAPIKeyException,
                RateLimitedException,
                UnknownException,
            ) as error:
                raise UpdateFailed from error

        return data
