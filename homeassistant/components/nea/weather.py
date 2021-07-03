"""Support for SG National Environment Agency weather service."""
from datetime import datetime, timezone
import logging

import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    PLATFORM_SCHEMA,
    WeatherEntity,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
)
from homeassistant.helpers import config_validation as cv

# Reuse data and API logic from the sensor implementation
from .sensor import ATTRIBUTION, NEAData

_LOGGER = logging.getLogger(__name__)

CONDITION_CLASSES = {
    "cloudy": ["Cloudy", "Overcast"],
    "fog": ["Mist", "Fog", "Hazy", "Slightly Hazy"],
    "hail": [],
    "lightning": [],
    "lightning-rainy": [
        "Heavy Thundery Showers with Gusty Winds",
        "Heavy Thundery Showers",
        "Thundery Showers",
    ],
    "partlycloudy": ["Partly Cloudy (Day)", "Partly Cloudy (Night)"],
    "pouring": ["Heavy Rain", "Heavy Showers"],
    "rainy": [
        "Drizzle",
        "Light Rain",
        "Light Showers",
        "Passing Showers",
        "Moderate Rain",
        "Showers",
        "Strong Winds, Showers",
        "Strong Winds, Rain",
        "Windy, Rain",
        "Windy, Showers",
    ],
    "snowy": ["Snow"],
    "snowy-rainy": ["Snow Showers"],
    "sunny": ["Sunny"],
    "windy": ["Strong Winds", "Windy, Cloudy", "Windy", "Windy, Fair"],
    "windy-variant": [],
    "exceptional": ["Fair (Day)", "Fair (Night)", "Fair & Warm"],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default="NEA"): cv.string,
        vol.Inclusive(
            CONF_LATITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.latitude,
        vol.Inclusive(
            CONF_LONGITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.longitude,
    }
)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the NEA weather platform."""
    name = config.get(CONF_NAME)
    lat = config.get(CONF_LATITUDE, hass.config.latitude)
    lon = config.get(CONF_LONGITUDE, hass.config.longitude)

    if None in (lat, lon):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    add_devices([NEAWeather(name, lat, lon)], True)


class NEAWeather(WeatherEntity):
    """Implementation of a NEA weather condition."""

    def __init__(self, name, lat, lon):
        """Initialise the platform with a data instance and site."""
        self._name = name
        self.fclastupdate = datetime.min.replace(tzinfo=timezone.utc)
        self.dataset = {}

        for sensor_type in [
            "2-hour-weather-forecast",
            "24-hour-weather-forecast",
            "4-day-weather-forecast",
            "air-temperature",
            "relative-humidity",
            "wind-speed",
            "wind-direction",
        ]:
            self.dataset[sensor_type] = NEAData(sensor_type, lat, lon)

    def update(self):
        """Update current conditions."""
        for data in self.dataset.values():
            data.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"station": self.dataset["2-hour-weather-forecast"].station["name"]}

    @property
    def condition(self):
        """Return the current condition."""
        data = self.dataset["2-hour-weather-forecast"]
        for key, value in CONDITION_CLASSES.items():
            if data.state in value:
                return key
        return STATE_UNKNOWN

    # Now implement the WeatherEntity interface

    @property
    def temperature(self):
        """Return the platform temperature."""
        return self.dataset["air-temperature"].state

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def humidity(self):
        """Return the relative humidity."""
        return self.dataset["relative-humidity"].state

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self.dataset["wind-speed"].state

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self.dataset["wind-direction"].state

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast array."""
        # Check if forecast array needs updating
        if self.fclastupdate < datetime.strptime(
            self.dataset["24-hour-weather-forecast"].data["items"][0][
                "update_timestamp"
            ],
            "%Y-%m-%dT%H:%M:%S%z",
        ) or self.fclastupdate < datetime.strptime(
            self.dataset["4-day-weather-forecast"].data["items"][0]["update_timestamp"],
            "%Y-%m-%dT%H:%M:%S%z",
        ):
            forecasts = []
            # Insert 24hour forecast into array
            forecast = self.dataset["24-hour-weather-forecast"].data["items"][0]
            condition = STATE_UNKNOWN
            for key, value in CONDITION_CLASSES.items():
                if forecast["general"]["forecast"] in value:
                    condition = key
                    break
            forecasts.append(
                {
                    ATTR_FORECAST_TIME: forecast["valid_period"]["start"],
                    ATTR_FORECAST_CONDITION: condition,
                    ATTR_FORECAST_TEMP_LOW: forecast["general"]["temperature"]["low"],
                    ATTR_FORECAST_TEMP: forecast["general"]["temperature"]["high"],
                }
            )
            # Insert 4day forecasts into array
            for forecast in self.dataset["4-day-weather-forecast"].data["items"][0][
                "forecasts"
            ]:

                def lookup_condition():
                    for key, value in CONDITION_CLASSES.items():
                        for cond in value:
                            if cond.lower() in forecast["forecast"]:
                                return key
                    return STATE_UNKNOWN

                forecasts.append(
                    {
                        ATTR_FORECAST_TIME: datetime.strftime(
                            forecast["date"], "%Y-%m-%d"
                        ),
                        ATTR_FORECAST_CONDITION: lookup_condition(),
                        ATTR_FORECAST_TEMP_LOW: forecast["temperature"]["low"],
                        ATTR_FORECAST_TEMP: forecast["temperature"]["high"],
                    }
                )
        return forecasts
