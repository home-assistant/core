"""Support for SG National Environment Agency weather service."""
from datetime import datetime, timedelta
import logging

from datagovsg.environment.constants import ENVIRONMENT_API_ENDPOINT
from datagovsg.exceptions import APIError
from datagovsg.net import send_request
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
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
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    DEGREE,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    SPEED_KILOMETERS_PER_HOUR,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    UV_INDEX,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by NEA"

INTERVALS = {
    "2-hour-weather-forecast": timedelta(minutes=30),
    "24-hour-weather-forecast": timedelta(hours=1),
    "4-day-weather-forecast": timedelta(hours=1),
    "air-temperature": timedelta(minutes=1),
    "pm25": timedelta(hours=1),
    "psi": timedelta(hours=1),
    "rainfall": timedelta(minutes=5),
    "relative-humidity": timedelta(minutes=1),
    "uv-index": timedelta(hours=1),
    "wind-direction": timedelta(minutes=1),
    "wind-speed": timedelta(minutes=1),
}

# Sensor types are defined like so:
# Name, units
SENSOR_TYPES = {
    "2-hour-weather-forecast": ["Weather", None, None],
    "air-temperature": ["Temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "pm25": ["PM2.5", CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, "mdi:biohazard"],
    "psi": ["PSI", None, "mdi:biohazard"],
    "rainfall": ["Rainfall", LENGTH_MILLIMETERS, "mdi:weather-pouring"],
    "relative-humidity": ["Humidity", PERCENTAGE, "mdi:water-percent"],
    "uv-index": ["UV Index", UV_INDEX, "mdi:weather-sunny"],
    "wind-direction": ["Wind Direction", DEGREE, "mdi:compass-outline"],
    "wind-speed": ["Wind Speed", SPEED_KILOMETERS_PER_HOUR, "mdi:weather-windy"],
}

CONDITION_CLASSES = {
    ATTR_CONDITION_CLEAR_NIGHT: ["Fair (Night)"],
    ATTR_CONDITION_CLOUDY: ["Cloudy", "Overcast"],
    ATTR_CONDITION_EXCEPTIONAL: ["Fair (Day)", "Fair & Warm"],
    ATTR_CONDITION_FOG: ["Mist", "Fog", "Hazy", "Slightly Hazy"],
    ATTR_CONDITION_HAIL: [],
    ATTR_CONDITION_LIGHTNING: [],
    ATTR_CONDITION_LIGHTNING_RAINY: [
        "Heavy Thundery Showers with Gusty Winds",
        "Heavy Thundery Showers",
        "Thundery Showers",
    ],
    ATTR_CONDITION_PARTLYCLOUDY: ["Partly Cloudy (Day)", "Partly Cloudy (Night)"],
    ATTR_CONDITION_POURING: ["Heavy Rain", "Heavy Showers"],
    ATTR_CONDITION_RAINY: [
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
    ATTR_CONDITION_SNOWY: ["Snow"],
    ATTR_CONDITION_SNOWY_RAINY: ["Snow Showers"],
    ATTR_CONDITION_SUNNY: ["Sunny"],
    ATTR_CONDITION_WINDY: ["Strong Winds", "Windy, Cloudy", "Windy", "Windy, Fair"],
    ATTR_CONDITION_WINDY_VARIANT: [],
}

CONDITION_ICONS = {
    ATTR_CONDITION_CLEAR_NIGHT: "mdi:weather-night",
    ATTR_CONDITION_CLOUDY: "mdi:weather-cloudy",
    ATTR_CONDITION_EXCEPTIONAL: "mdi:weather-sunny",
    ATTR_CONDITION_FOG: "mdi:weather-fog",
    ATTR_CONDITION_HAIL: "mdi:weather-hail",
    ATTR_CONDITION_LIGHTNING: "mdi:weather-lightning",
    ATTR_CONDITION_LIGHTNING_RAINY: "mdi:weather-lightning-rainy",
    ATTR_CONDITION_PARTLYCLOUDY: "mdi:weather-partly-cloudy",
    ATTR_CONDITION_POURING: "mdi:weather-pouring",
    ATTR_CONDITION_RAINY: "mdi:weather-rainy",
    ATTR_CONDITION_SNOWY: "mdi:weather-snowy",
    ATTR_CONDITION_SNOWY_RAINY: "mdi:weather-snowy-rainy",
    ATTR_CONDITION_SUNNY: "mdi:weather-sunny",
    ATTR_CONDITION_WINDY: "mdi:weather-windy",
    ATTR_CONDITION_WINDY_VARIANT: "mdi:weather-windy-variant",
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_CONDITIONS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
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
    """Set up the NEA sensor."""
    name = config.get(CONF_NAME)
    lat = config.get(CONF_LATITUDE, hass.config.latitude)
    lon = config.get(CONF_LONGITUDE, hass.config.longitude)

    if None in (lat, lon):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    add_devices(
        [
            NEASensor(variable, name, lat, lon)
            for variable in config[CONF_MONITORED_CONDITIONS]
        ],
        True,
    )


class NEASensor(Entity):
    """Implementation of a NEA sensor."""

    def __init__(self, sensor_type, name, lat, lon):
        """Initialize the sensor."""
        self.client_name = name
        self._name = SENSOR_TYPES[sensor_type][0]
        self.type = sensor_type
        self.data = NEAData(sensor_type, lat, lon)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.data.state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self.type == "2-hour-weather-forecast":
            return CONDITION_ICONS[self.data.state]
        else:
            return SENSOR_TYPES[self.type][2]

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        if self.type != "uv-index":
            attr["Station Name"] = self.data.station["name"]
        attr["Reading Taken"] = datetime.strptime(
            self.data.data["items"][0]["timestamp"],
            "%Y-%m-%dT%H:%M:%S%z",
        )
        attr[ATTR_ATTRIBUTION] = ATTRIBUTION
        return attr

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_TYPES[self.type][1]

    def update(self):
        """Update current conditions."""
        self.data.update()


class NEAData:
    """Get the latest data from NEA."""

    def __init__(self, sensor_type, lat, lon):
        """Initialize the data object."""
        self.type = sensor_type
        self.lat = lat
        self.lon = lon
        self.data = None
        self.state = STATE_UNKNOWN
        self.station = None
        self.update = Throttle(INTERVALS[sensor_type])(self._update)

    def _update(self):
        """Get the latest data from NEA."""
        try:
            self.data = send_request(f"{ENVIRONMENT_API_ENDPOINT}/{self.type}")
            if self.type not in (
                "24-hour-weather-forecast",
                "4-day-weather-forecast",
            ):
                if self.type != "uv-index":
                    self.station = self._closest_station()
                if self.type == "2-hour-weather-forecast":
                    for forecast in self.data["items"][0]["forecasts"]:
                        if forecast["area"] == self.station["name"]:
                            for key, value in CONDITION_CLASSES.items():
                                if forecast["forecast"] in value:
                                    self.state = key
                                    break
                            break
                elif self.type == "uv-index":
                    self.state = self.data["items"][0]["index"][0]["value"]
                else:
                    data = self.data["items"][0]["readings"]
                    if self.type == "pm25":
                        self.state = data["pm25_one_hourly"][self.station["name"]]
                    elif self.type == "psi":
                        self.state = data["psi_twenty_four_hourly"][
                            self.station["name"]
                        ]
                    else:
                        for reading in data:
                            if reading["station_id"] == self.station["id"]:
                                if self.type == "wind-speed":
                                    # Convert knots to km/h
                                    self.state = reading["value"] * 1.852
                                else:
                                    self.state = reading["value"]
                                break
        except APIError as api_err:
            _LOGGER.error("API Error: %s", api_err)
        except RequestException as err:
            _LOGGER.error("Failed to connect: %s", err)

    def _closest_station(self):
        """Return the closest station to our lat/lon."""
        if self.type in ("pm25", "psi"):
            stations = self.data["region_metadata"]
        elif self.type == "2-hour-weather-forecast":
            stations = self.data["area_metadata"]
        else:
            stations = self.data["metadata"]["stations"]

        def comparable_dist(station):
            """Create a psudeo-distance from lat/lon."""
            if self.type in ("pm25", "psi", "2-hour-weather-forecast"):
                station_lat = station["label_location"]["latitude"]
                station_lon = station["label_location"]["longitude"]
            else:
                station_lat = station["location"]["latitude"]
                station_lon = station["location"]["longitude"]
            return (self.lat - station_lat) ** 2 + (self.lon - station_lon) ** 2

        return min(stations, key=comparable_dist)
