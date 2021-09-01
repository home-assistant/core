"""Weather information for air and road temperature (by Trafikverket)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

import aiohttp
from pytrafikverket.trafikverket_weather import TrafikverketWeather
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_API_KEY,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    DEGREE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    SPEED_METERS_PER_SECOND,
    TEMP_CELSIUS,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by Trafikverket"
ATTR_MEASURE_TIME = "measure_time"
ATTR_ACTIVE = "active"

CONF_STATION = "station"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)

SCAN_INTERVAL = timedelta(seconds=300)


@dataclass
class TrafikverketRequiredKeysMixin:
    """Mixin for required keys."""

    api_key: str


@dataclass
class TrafikverketSensorEntityDescription(
    SensorEntityDescription, TrafikverketRequiredKeysMixin
):
    """Describes Trafikverket sensor entity."""


SENSOR_TYPES: tuple[TrafikverketSensorEntityDescription, ...] = (
    TrafikverketSensorEntityDescription(
        key="air_temp",
        api_key="air_temp",
        name="Air temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        icon="mdi:thermometer",
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    TrafikverketSensorEntityDescription(
        key="road_temp",
        api_key="road_temp",
        name="Road temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        icon="mdi:thermometer",
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    TrafikverketSensorEntityDescription(
        key="precipitation",
        api_key="precipitationtype",
        name="Precipitation type",
        icon="mdi:weather-snowy-rainy",
    ),
    TrafikverketSensorEntityDescription(
        key="wind_direction",
        api_key="winddirection",
        name="Wind direction",
        native_unit_of_measurement=DEGREE,
        icon="mdi:flag-triangle",
    ),
    TrafikverketSensorEntityDescription(
        key="wind_direction_text",
        api_key="winddirectiontext",
        name="Wind direction text",
        icon="mdi:flag-triangle",
    ),
    TrafikverketSensorEntityDescription(
        key="wind_speed",
        api_key="windforce",
        name="Wind speed",
        native_unit_of_measurement=SPEED_METERS_PER_SECOND,
        icon="mdi:weather-windy",
    ),
    TrafikverketSensorEntityDescription(
        key="wind_speed_max",
        api_key="windforcemax",
        name="Wind speed max",
        native_unit_of_measurement=SPEED_METERS_PER_SECOND,
        icon="mdi:weather-windy-variant",
    ),
    TrafikverketSensorEntityDescription(
        key="humidity",
        api_key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
        device_class=DEVICE_CLASS_HUMIDITY,
    ),
    TrafikverketSensorEntityDescription(
        key="precipitation_amount",
        api_key="precipitation_amount",
        name="Precipitation amount",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:cup-water",
    ),
    TrafikverketSensorEntityDescription(
        key="precipitation_amountname",
        api_key="precipitation_amountname",
        name="Precipitation name",
        icon="mdi:weather-pouring",
    ),
)

SENSOR_KEYS = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_STATION): cv.string,
        vol.Required(CONF_MONITORED_CONDITIONS, default=[]): [vol.In(SENSOR_KEYS)],
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Trafikverket sensor platform."""

    sensor_name = config[CONF_NAME]
    sensor_api = config[CONF_API_KEY]
    sensor_station = config[CONF_STATION]

    web_session = async_get_clientsession(hass)

    weather_api = TrafikverketWeather(web_session, sensor_api)

    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    entities = [
        TrafikverketWeatherStation(
            weather_api, sensor_name, sensor_station, description
        )
        for description in SENSOR_TYPES
        if description.key in monitored_conditions
    ]

    async_add_entities(entities, True)


class TrafikverketWeatherStation(SensorEntity):
    """Representation of a Trafikverket sensor."""

    entity_description: TrafikverketSensorEntityDescription

    def __init__(
        self,
        weather_api,
        name,
        sensor_station,
        description: TrafikverketSensorEntityDescription,
    ):
        """Initialize the sensor."""
        self.entity_description = description
        self._attr_name = f"{name} {description.name}"
        self._station = sensor_station
        self._weather_api = weather_api
        self._weather = None

    @property
    def extra_state_attributes(self):
        """Return the state attributes of Trafikverket Weatherstation."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_ACTIVE: self._weather.active,
            ATTR_MEASURE_TIME: self._weather.measure_time,
        }

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from Trafikverket and updates the states."""
        try:
            self._weather = await self._weather_api.async_get_weather(self._station)
            self._attr_native_value = getattr(
                self._weather, self.entity_description.api_key
            )
        except (asyncio.TimeoutError, aiohttp.ClientError, ValueError) as error:
            _LOGGER.error("Could not fetch weather data: %s", error)
