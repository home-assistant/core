"""Support for IPMA weather service."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from pyipma.api import IPMA_API
from pyipma.location import Location
import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    PLATFORM_SCHEMA,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
    PRESSURE_HPA,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
from homeassistant.util.dt import now, parse_datetime

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Instituto Português do Mar e Atmosfera"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)

CONDITION_CLASSES = {
    ATTR_CONDITION_CLOUDY: [4, 5, 24, 25, 27],
    ATTR_CONDITION_FOG: [16, 17, 26],
    ATTR_CONDITION_HAIL: [21, 22],
    ATTR_CONDITION_LIGHTNING: [19],
    ATTR_CONDITION_LIGHTNING_RAINY: [20, 23],
    ATTR_CONDITION_PARTLYCLOUDY: [2, 3],
    ATTR_CONDITION_POURING: [8, 11],
    ATTR_CONDITION_RAINY: [6, 7, 9, 10, 12, 13, 14, 15],
    ATTR_CONDITION_SNOWY: [18],
    ATTR_CONDITION_SNOWY_RAINY: [],
    ATTR_CONDITION_SUNNY: [1],
    ATTR_CONDITION_WINDY: [],
    ATTR_CONDITION_WINDY_VARIANT: [],
    ATTR_CONDITION_EXCEPTIONAL: [],
}

FORECAST_MODE = ["hourly", "daily"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_MODE, default="daily"): vol.In(FORECAST_MODE),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ipma platform.

    Deprecated.
    """
    _LOGGER.warning("Loading IPMA via platform config is deprecated")

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return

    api = await async_get_api(hass)
    location = await async_get_location(hass, api, latitude, longitude)

    async_add_entities([IPMAWeather(location, api, config)], True)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a weather entity from a config_entry."""
    latitude = config_entry.data[CONF_LATITUDE]
    longitude = config_entry.data[CONF_LONGITUDE]
    mode = config_entry.data[CONF_MODE]

    api = await async_get_api(hass)
    location = await async_get_location(hass, api, latitude, longitude)

    # Migrate old unique_id
    @callback
    def _async_migrator(entity_entry: entity_registry.RegistryEntry):
        # Reject if new unique_id
        if entity_entry.unique_id.count(",") == 2:
            return None

        new_unique_id = (
            f"{location.station_latitude}, {location.station_longitude}, {mode}"
        )

        _LOGGER.info(
            "Migrating unique_id from [%s] to [%s]",
            entity_entry.unique_id,
            new_unique_id,
        )
        return {"new_unique_id": new_unique_id}

    await entity_registry.async_migrate_entries(
        hass, config_entry.entry_id, _async_migrator
    )

    async_add_entities([IPMAWeather(location, api, config_entry.data)], True)


async def async_get_api(hass):
    """Get the pyipma api object."""
    websession = async_get_clientsession(hass)
    return IPMA_API(websession)


async def async_get_location(hass, api, latitude, longitude):
    """Retrieve pyipma location, location name to be used as the entity name."""
    async with async_timeout.timeout(30):
        location = await Location.get(api, float(latitude), float(longitude))

    _LOGGER.debug(
        "Initializing for coordinates %s, %s -> station %s (%d, %d)",
        latitude,
        longitude,
        location.station,
        location.id_station,
        location.global_id_local,
    )

    return location


class IPMAWeather(WeatherEntity):
    """Representation of a weather condition."""

    _attr_native_pressure_unit = PRESSURE_HPA
    _attr_native_temperature_unit = TEMP_CELSIUS
    _attr_native_wind_speed_unit = SPEED_KILOMETERS_PER_HOUR

    def __init__(self, location: Location, api: IPMA_API, config):
        """Initialise the platform with a data instance and station name."""
        self._api = api
        self._location_name = config.get(CONF_NAME, location.name)
        self._mode = config.get(CONF_MODE)
        self._location = location
        self._observation = None
        self._forecast = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Update Condition and Forecast."""
        async with async_timeout.timeout(10):
            new_observation = await self._location.observation(self._api)
            new_forecast = await self._location.forecast(self._api)

            if new_observation:
                self._observation = new_observation
            else:
                _LOGGER.warning("Could not update weather observation")

            if new_forecast:
                self._forecast = new_forecast
            else:
                _LOGGER.warning("Could not update weather forecast")

            _LOGGER.debug(
                "Updated location %s, observation %s",
                self._location.name,
                self._observation,
            )

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return f"{self._location.station_latitude}, {self._location.station_longitude}, {self._mode}"

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def name(self):
        """Return the name of the station."""
        return self._location_name

    @property
    def condition(self):
        """Return the current condition."""
        if not self._forecast:
            return

        return next(
            (
                k
                for k, v in CONDITION_CLASSES.items()
                if self._forecast[0].weather_type in v
            ),
            None,
        )

    @property
    def native_temperature(self):
        """Return the current temperature."""
        if not self._observation:
            return None

        return self._observation.temperature

    @property
    def native_pressure(self):
        """Return the current pressure."""
        if not self._observation:
            return None

        return self._observation.pressure

    @property
    def humidity(self):
        """Return the name of the sensor."""
        if not self._observation:
            return None

        return self._observation.humidity

    @property
    def native_wind_speed(self):
        """Return the current windspeed."""
        if not self._observation:
            return None

        return self._observation.wind_intensity_km

    @property
    def wind_bearing(self):
        """Return the current wind bearing (degrees)."""
        if not self._observation:
            return None

        return self._observation.wind_direction

    @property
    def forecast(self):
        """Return the forecast array."""
        if not self._forecast:
            return []

        if self._mode == "hourly":
            forecast_filtered = [
                x
                for x in self._forecast
                if x.forecasted_hours == 1
                and parse_datetime(x.forecast_date)
                > (now().utcnow() - timedelta(hours=1))
            ]

            fcdata_out = [
                {
                    ATTR_FORECAST_TIME: data_in.forecast_date,
                    ATTR_FORECAST_CONDITION: next(
                        (
                            k
                            for k, v in CONDITION_CLASSES.items()
                            if int(data_in.weather_type) in v
                        ),
                        None,
                    ),
                    ATTR_FORECAST_NATIVE_TEMP: float(data_in.feels_like_temperature),
                    ATTR_FORECAST_PRECIPITATION_PROBABILITY: (
                        int(float(data_in.precipitation_probability))
                        if int(float(data_in.precipitation_probability)) >= 0
                        else None
                    ),
                    ATTR_FORECAST_NATIVE_WIND_SPEED: data_in.wind_strength,
                    ATTR_FORECAST_WIND_BEARING: data_in.wind_direction,
                }
                for data_in in forecast_filtered
            ]
        else:
            forecast_filtered = [f for f in self._forecast if f.forecasted_hours == 24]
            fcdata_out = [
                {
                    ATTR_FORECAST_TIME: data_in.forecast_date,
                    ATTR_FORECAST_CONDITION: next(
                        (
                            k
                            for k, v in CONDITION_CLASSES.items()
                            if int(data_in.weather_type) in v
                        ),
                        None,
                    ),
                    ATTR_FORECAST_NATIVE_TEMP_LOW: data_in.min_temperature,
                    ATTR_FORECAST_NATIVE_TEMP: data_in.max_temperature,
                    ATTR_FORECAST_PRECIPITATION_PROBABILITY: data_in.precipitation_probability,
                    ATTR_FORECAST_NATIVE_WIND_SPEED: data_in.wind_strength,
                    ATTR_FORECAST_WIND_BEARING: data_in.wind_direction,
                }
                for data_in in forecast_filtered
            ]

        return fcdata_out
