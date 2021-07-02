"""Support for SG National Environment Agency weather service."""
from datetime import datetime, timezone
import logging

import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_FORECAST_TEMP,
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

ATTR_FORECAST_CONDITION = "condition"
ATTR_FORECAST_TEMP_LOW = "templow"

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
        self.fcarray = []
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
            data = NEAData(sensor_type, lat, lon)
            data.update()
            if sensor_type == "4-day-weather-forecast":
                self.dataset.update({sensor_type: [data]})
            else:
                self.dataset.update({sensor_type: [data, data.closest_station()]})

    def update(self):
        """Update current conditions."""
        for _, value in self.dataset.items():
            value[0].update()

    @property
    def name(self):
        """Return the name of the sensor."""
        if self._name is None:
            return self.dataset["2-hour-weather-forecast"][1]["name"]
        return self._name

    @property
    def condition(self):
        """Return the current condition."""
        for forecast in self.dataset["2-hour-weather-forecast"][0].data["items"][0][
            "forecasts"
        ]:
            if forecast["area"] == self.dataset["2-hour-weather-forecast"][1]["name"]:
                for key, value in CONDITION_CLASSES.items():
                    if forecast["forecast"] in value:
                        return key
        return STATE_UNKNOWN

    # Now implement the WeatherEntity interface

    @property
    def temperature(self):
        """Return the platform temperature."""
        for i in self.dataset["air-temperature"][0].data["items"][0]["readings"]:
            if i["station_id"] == self.dataset["air-temperature"][1]["id"]:
                return i["value"]
        return STATE_UNKNOWN

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def humidity(self):
        """Return the relative humidity."""
        for i in self.dataset["relative-humidity"][0].data["items"][0]["readings"]:
            if i["station_id"] == self.dataset["relative-humidity"][1]["id"]:
                return i["value"]
        return STATE_UNKNOWN

    @property
    def wind_speed(self):
        """Return the wind speed."""
        for i in self.dataset["wind-speed"][0].data["items"][0]["readings"]:
            if i["station_id"] == self.dataset["wind-speed"][1]["id"]:
                return i["value"]
        return STATE_UNKNOWN

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        for i in self.dataset["wind-direction"][0].data["items"][0]["readings"]:
            if i["station_id"] == self.dataset["wind-direction"][1]["id"]:
                return i["value"]
        return STATE_UNKNOWN

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast array."""
        # Check if forecast array needs updating
        if self.fclastupdate < datetime.strptime(
            "".join(
                self.dataset["24-hour-weather-forecast"][0]
                .data["items"][0]["update_timestamp"]
                .rsplit(":", 1)
            ),
            "%Y-%m-%dT%H:%M:%S%z",
        ) or self.fclastupdate < datetime.strptime(
            "".join(
                self.dataset["4-day-weather-forecast"][0]
                .data["items"][0]["update_timestamp"]
                .rsplit(":", 1)
            ),
            "%Y-%m-%dT%H:%M:%S%z",
        ):
            _24hfc = []
            _4dfc = []
            # Build 24hour forecast array
            for period in self.dataset["24-hour-weather-forecast"][0].data["items"][0][
                "periods"
            ]:
                for key, value in CONDITION_CLASSES.items():
                    if (
                        period["regions"][
                            self.dataset["24-hour-weather-forecast"][1]["name"]
                        ]
                        in value
                    ):
                        condition = key
                        break
                start = datetime.strptime(
                    "".join(period["time"]["start"].rsplit(":", 1)),
                    "%Y-%m-%dT%H:%M:%S%z",
                )
                end = datetime.strptime(
                    "".join(period["time"]["end"].rsplit(":", 1)), "%Y-%m-%dT%H:%M:%S%z"
                )
                _24hfc.append(
                    {
                        ATTR_FORECAST_TIME: start + (end - start) / 2,
                        ATTR_FORECAST_CONDITION: condition,
                        ATTR_FORECAST_TEMP_LOW: self.dataset[
                            "24-hour-weather-forecast"
                        ][0].data["items"][0]["general"]["temperature"]["low"],
                        ATTR_FORECAST_TEMP: self.dataset["24-hour-weather-forecast"][
                            0
                        ].data["items"][0]["general"]["temperature"]["high"],
                    }
                )
            # Build 4day forecast array
            for forecast in self.dataset["4-day-weather-forecast"][0].data["items"][0][
                "forecasts"
            ][1:]:
                found = False
                for key, value in CONDITION_CLASSES.items():
                    for cond in value:
                        if cond.lower() in forecast["forecast"]:
                            condition = key
                            found = True
                            break
                    if found is True:
                        break
                _4dfc.append(
                    {
                        ATTR_FORECAST_TIME: datetime.strftime(
                            forecast["date"], "%Y-%m-%d"
                        ),
                        ATTR_FORECAST_CONDITION: condition,
                        ATTR_FORECAST_TEMP_LOW: forecast["temperature"]["low"],
                        ATTR_FORECAST_TEMP: forecast["temperature"]["high"],
                    }
                )
            # Combine and update forecast array
            self.fcarray = _24hfc + _4dfc
        return self.fcarray
