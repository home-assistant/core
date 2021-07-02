"""Support for SG National Environment Agency weather service."""
from datetime import datetime, timedelta
import logging

from datagovsg.environment.constants import ENVIRONMENT_API_ENDPOINT
from datagovsg.exceptions import APIError
from datagovsg.net import send_request
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    TEMP_CELSIUS,
    UV_INDEX,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by NEA"

# Sensor types are defined like so:
# Name, units
SENSOR_TYPES = {
    "2-hour-weather-forecast": ["Weather", None],
    "air-temperature": ["Temperature", TEMP_CELSIUS],
    "pm25": ["PM2.5", "µg/m³"],
    "psi": ["PSI", None],
    "rainfall": ["Rainfall", "mm"],
    "relative-humidity": ["Humidity", "%"],
    "uv-index": ["UV Index", UV_INDEX],
    "wind-direction": ["Wind Direction", "°"],
    "wind-speed": ["Wind Speed", "kt"],
}

REGION_METADATA = [
    {"name": "west", "location": {"latitude": 1.35735, "longitude": 103.7}},
    {"name": "east", "location": {"latitude": 1.35735, "longitude": 103.94}},
    {"name": "central", "location": {"latitude": 1.35735, "longitude": 103.82}},
    {"name": "south", "location": {"latitude": 1.29587, "longitude": 103.82}},
    {"name": "north", "location": {"latitude": 1.41803, "longitude": 103.82}},
]

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
        self._state = None
        self.data = NEAData(sensor_type, lat, lon)
        self.data.update()
        self.interval = self.set_interval()
        self.update = Throttle(self.interval)(self._update)
        if sensor_type != "uv-index":
            self.station = self.data.closest_station()

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        if self.type != "uv-index":
            attr["Station Name"] = self.station["name"]
        attr["Reading Taken"] = datetime.strptime(
            "".join(self.data.data["items"][0]["timestamp"].rsplit(":", 1)),
            "%Y-%m-%dT%H:%M:%S%z",
        )
        attr[ATTR_ATTRIBUTION] = ATTRIBUTION
        return attr

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_TYPES[self.type][1]

    def _update(self):
        """Update current conditions."""
        self.data.update()
        if self.type == "2-hour-weather-forecast":
            for i in self.data.data["items"][0]["forecasts"]:
                if i["area"] == self.station["name"]:
                    self._state = i["forecast"]
                    break
        elif self.type == "pm25":
            for key, value in self.data.data["items"][0]["readings"][
                "pm25_one_hourly"
            ].items():
                if key == self.station["name"]:
                    self._state = value
                    break
        elif self.type == "psi":
            for key, value in self.data.data["items"][0]["readings"][
                "psi_twenty_four_hourly"
            ].items():
                if key == self.station["name"]:
                    self._state = value
                    break
        elif self.type == "uv-index":
            self._state = self.data.data["items"][0]["index"][0]["value"]
        else:
            for i in self.data.data["items"][0]["readings"]:
                if i["station_id"] == self.station["id"]:
                    self._state = i["value"]
                    break

    def set_interval(self):
        """Return the interval depending on sensor_type."""
        if self.type == "2-hour-weather-forecast":
            return timedelta(minutes=30)
        if self.type in ("pm25", "psi", "uv-index"):
            return timedelta(hours=1)
        if self.type == "rainfall":
            return timedelta(minutes=5)
        return timedelta(minutes=1)


class NEAData:
    """Get the latest data from NEA."""

    def __init__(self, sensor_type, lat, lon):
        """Initialize the data object."""
        self.type = sensor_type
        self.lat = lat
        self.lon = lon
        self.data = None

    def update(self):
        """Get the latest data from NEA."""
        try:
            self.data = send_request(f"{ENVIRONMENT_API_ENDPOINT}/{self.type}")
        except APIError as api_err:
            _LOGGER.error("API Error: %s", api_err)
        except RequestException as err:
            _LOGGER.error("Failed to connect: %s", err)

    def closest_station(self):
        """Return the closest station to our lat/lon."""
        if self.type in ("pm25", "psi"):
            stations = self.data["region_metadata"]
        elif self.type == "2-hour-weather-forecast":
            stations = self.data["area_metadata"]
        elif self.type == "24-hour-weather-forecast":
            stations = REGION_METADATA
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
