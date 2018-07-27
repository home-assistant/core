"""
Support for the Weather Underground (Wunderground) service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/weather.wunderground/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.helpers.typing import HomeAssistantType, ConfigType
from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION, ATTR_FORECAST_PRECIPITATION, ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW, ATTR_FORECAST_TIME, PLATFORM_SCHEMA, WeatherEntity)
from homeassistant.const import (
    CONF_API_KEY, TEMP_CELSIUS, CONF_LATITUDE, CONF_LONGITUDE,
    CONF_NAME, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor.wunderground import (
    SENSOR_TYPES, WUndergroundData
)

_LOGGER = logging.getLogger(__name__)

ATTR_FORECAST_WIND_SPEED = 'wind_speed'
ATTR_FORECAST_WIND_BEARING = 'wind_bearing'

ATTRIBUTION = 'Data provided by Weather Underground'

CONF_PWS_ID = 'pws_id'

DEFAULT_NAME = 'Weather Underground'

CONDITION_CLASSES = {
    'cloudy': [
        'Overcast',
        'Mostly Cloudy',
    ],
    'fog': [
        'Patches of Fog',
        'Shallow Fog',
        'Partial Fog',
        'Fog',
        'Light Fog',
        'Heavy Fog',
        'Fog Patches',
        'Light Fog Patches',
        'Heavy Fog Patches',
        'Mist',
        'Light Mist',
        'Heavy Mist',
        'Rain Mist',
        'Light Rain Mist',
        'Heavy Rain Mist'
        'Freezing Fog',
        'Light Freezing Fog',
        'Heavy Freezing Fog',
    ],
    'hail': [
        'Hail',
        'Light Hail',
        'Heavy Hail',
        'Small Hail',
        'Hail Showers',
        'Light Hail Showers',
        'Heavy Hail Showers',
        'Small Hail Showers',
        'Light Small Hail Showers',
        'Heavy Small Hail Showers',
    ],
    'lightning': [
        'Thunderstorm',
        'Light Thunderstorm',
        'Heavy Thunderstorm',
    ],
    'lightning-rainy': [
        'Thunderstorms and Rain',
        'Light Thunderstorms and Rain',
        'Heavy Thunderstorms and Rain',
        'Thunderstorms and Snow',
        'Light Thunderstorms and Snow',
        'Heavy Thunderstorms and Snow',
        'Thunderstorms and Ice Pellets',
        'Light Thunderstorms and Ice Pellets',
        'Heavy Thunderstorms and Ice Pellets',
        'Thunderstorms with Hail',
        'Light Thunderstorms with Hail',
        'Heavy Thunderstorms with Hail',
        'Thunderstorms with Small Hail',
        'Light Thunderstorms with Small Hail',
        'Heavy Thunderstorms with Small Hail',
    ],
    'partlycloudy': [
        'Partly Cloudy',
        'Scattered Clouds',
    ],
    'pouring': [
        'Heavy Rain',
        'Heavy Rain Showers',
        'Heavy Freezing Rain',
    ],
    'rainy': [
        'Drizzle',
        'Light Drizzle',
        'Heavy Drizzle',
        'Rain',
        'Light Rain',
        'Rain Showers',
        'Light Rain Showers',
        'Freezing Drizzle',
        'Light Freezing Drizzle',
        'Heavy Freezing Drizzle',
        'Freezing Rain',
        'Light Freezing Rain',
        'Unknown Precipitation',
    ],
    'snowy': [
        'Snow',
        'Light Snow',
        'Heavy Snow',
        'Snow Showers',
        'Light Snow Showers',
        'Heavy Snow Showers',
        'Blowing Snow',
        'Light Blowing Snow',
        'Heavy Blowing Snow',
    ],
    'snowy-rainy': [
        'Snow Grains',
        'Light Snow Grains',
        'Heavy Snow Grains',
        'Ice Crystals',
        'Light Ice Crystals',
        'Heavy Ice Crystals',
        'Ice Pellets',
        'Light Ice Pellets',
        'Heavy Ice Pellets',
        'Ice Pellet Showers',
        'Light Ice Pellet Showers',
        'Heavy Ice Pellet Showers',
    ],
    'sunny': [
        'Clear',
    ],
    'windy': [
        'Blowing Sand',
        'Light Blowing Sand',
        'Heavy Blowing Sand',
        'Blowing Widespread Dust',
        'Light Blowing Widespread Dust',
        'Heavy Blowing Widespread Dust',
        'Low Drifting Snow',
        'Light Low Drifting Snow',
        'Heavy Low Drifting Snow',
        'Low Drifting Widespread Dust',
        'Light Low Drifting Widespread Dust',
        'Heavy Low Drifting Widespread Dust',
        'Low Drifting Sand',
        'Light Low Drifting Sand',
        'Heavy Low Drifting Sand',
    ],
    'windy-variant': [
        'Snow Blowing Snow Mist',
        'Light Snow Blowing Snow Mist',
        'Heavy Snow Blowing Snow Mist',
        'Squalls',
        'Spray',
        'Light Spray',
        'Heavy Spray',
    ],
    'exceptional': [
        'Funnel Cloud',
        'Smoke',
        'Light Smoke',
        'Heavy Smoke',
        'Volcanic Ash',
        'Light Volcanic Ash',
        'Heavy Volcanic Ash',
        'Widespread Dust',
        'Light Widespread Dust',
        'Heavy Widespread Dust',
        'Sand',
        'Light Sand',
        'Heavy Sand',
        'Haze',
        'Light Haze',
        'Heavy Haze',
        'Dust Whirls',
        'Light Dust Whirls',
        'Heavy Dust Whirls',
        'Sandstorm',
        'Light Sandstorm',
        'Heavy Sandstorm',
    ],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_PWS_ID): cv.string,
    vol.Inclusive(CONF_LATITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.longitude,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_devices, discovery_info=None):
    """Set up the WUnderground weather platform."""
    name = config.get(CONF_NAME)
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    pws_id = config.get(CONF_PWS_ID)

    rest = WUndergroundData(
        hass, config.get(CONF_API_KEY), pws_id,
        'EN', latitude, longitude)

    rest.request_feature("conditions")
    rest.request_feature("forecast")

    async_add_devices([WUndergroundWeather(
        name, rest, hass.config.units.temperature_unit)], True)


class WUndergroundWeather(WeatherEntity):
    """Implementation of a Weather Underground weather component."""

    def __init__(self, name, wu, temperature_unit):
        """Initialize the sensor."""
        self._name = name
        self._wu = wu
        self._temperature_unit = temperature_unit
        self.data = None
        self.forecast_data = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def condition(self):
        """Return the current condition."""
        try:
            return [k for k, v in CONDITION_CLASSES.items() if
                    SENSOR_TYPES['weather'].value(self) in v][0]
        except IndexError:
            return STATE_UNKNOWN

    @property
    def temperature(self):
        """Return the temperature."""
        return SENSOR_TYPES['temp_c'].value(self)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the pressure."""
        return SENSOR_TYPES['pressure_mb'].value(self)

    @property
    def humidity(self):
        """Return the humidity."""
        return SENSOR_TYPES['relative_humidity'].value(self)

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return SENSOR_TYPES['wind_kph'].value(self)

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return SENSOR_TYPES['wind_degrees'].value(self)

    @property
    def visibility(self):
        """Return the visibility."""
        return SENSOR_TYPES['visibility_km'].value(self)

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast array."""
        data = []
        for entry in self.data['forecast']['simpleforecast']['forecastday']:
            data.append({
                ATTR_FORECAST_TIME:
                    int(entry['date']['epoch']) * 1000,
                ATTR_FORECAST_TEMP:
                    int(entry['high']['celsius']),
                ATTR_FORECAST_TEMP_LOW:
                    int(entry['low']['celsius']),
                ATTR_FORECAST_PRECIPITATION:
                    entry['qpf_allday']['mm'],
                ATTR_FORECAST_WIND_SPEED:
                    entry['avewind']['kph'],
                ATTR_FORECAST_WIND_BEARING:
                    entry['avewind']['degrees'],
                ATTR_FORECAST_CONDITION:
                    [k for k, v in CONDITION_CLASSES.items()
                     if entry['conditions'] in v][0]
            })
        return data

    @asyncio.coroutine
    def update(self):
        """Get the latest data from WUnderground."""
        yield from self._wu.async_update()

        self.data = self._wu.data
