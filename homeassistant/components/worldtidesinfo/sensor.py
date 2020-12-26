"""Support for the worldtides.info API v2."""
import base64
from datetime import timedelta
import logging
import time

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by WorldTides"

DEFAULT_NAME = "WorldTidesInfo"

SCAN_INTERVAL = timedelta(seconds=3600)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the WorldTidesInfo sensor."""
    name = config.get(CONF_NAME)

    lat = config.get(CONF_LATITUDE, hass.config.latitude)
    lon = config.get(CONF_LONGITUDE, hass.config.longitude)
    key = config.get(CONF_API_KEY)

    if None in (lat, lon):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")

    tides = WorldTidesInfoSensor(name, lat, lon, key)
    tides.update()
    if tides.data.get("error") == "No location found":
        _LOGGER.error("Location not available")
        return

    add_entities([tides])

class WorldTidesInfoSensor(Entity):
    """Representation of a WorldTidesInfo sensor."""

    def __init__(self, name, lat, lon, key):
        """Initialize the sensor."""
        self._name = name
        self._lat = lat
        self._lon = lon
        self._key = key
        self.data = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of this device."""
        attr = {ATTR_ATTRIBUTION: ATTRIBUTION}

        current_time = int(time.time())
        next_tide = 0
        for tide_index in range(len(self.data["extremes"])):
            if self.data["extremes"][tide_index]["dt"] < current_time:
                next_tide = tide_index
        next_tide = next_tide + 1

        if "High" in str(self.data["extremes"][next_tide]["type"]):
            attr["high_tide_time_utc"] = self.data["extremes"][next_tide]["date"]
            attr["high_tide_height"] = self.data["extremes"][next_tide]["height"]
            attr["low_tide_time_utc"] = self.data["extremes"][next_tide + 1]["date"]
            attr["low_tide_height"] = self.data["extremes"][next_tide + 1]["height"]
        elif "Low" in str(self.data["extremes"][next_tide]["type"]):
            attr["high_tide_time_utc"] = self.data["extremes"][next_tide + 1]["date"]
            attr["high_tide_height"] = self.data["extremes"][next_tide + 1]["height"]
            attr["low_tide_time_utc"] = self.data["extremes"][next_tide]["date"]
            attr["low_tide_height"] = self.data["extremes"][next_tide]["height"]
        filename2 = self.hass.config.path("www") + "/" + self._name + '.png'
        attr["plot"] = filename2

        std_string = "data:image/png;base64,"
        str_to_convert = self.data["plot"][len(std_string) : len(self.data["plot"])]
        imgdata = base64.b64decode(str_to_convert)

        with open(filename2, 'wb') as filehandler:
            filehandler.write(imgdata)

        return attr

    @property
    def state(self):
        """Return the state of the device."""
        if self.data:
            current_time = int(time.time())
            next_tide = 0
            for tide_index in range(len(self.data["extremes"])):
                if self.data["extremes"][tide_index]["dt"] < current_time:
                   next_tide = tide_index
            next_tide = next_tide + 1
            if "High" in str(self.data["extremes"][next_tide]["type"]):
                tidetime = time.strftime(
                    "%I:%M %p", time.localtime(self.data["extremes"][next_tide]["dt"])
                )
                return f"High tide at {tidetime}"
            if "Low" in str(self.data["extremes"][next_tide]["type"]):
                tidetime = time.strftime(
                    "%I:%M %p", time.localtime(self.data["extremes"][next_tide]["dt"])
                )
                return f"Low tide at {tidetime}"
            return None
        return None

    def update(self):
        """Get the latest data from WorldTidesInfo API v2."""
        resource = (
            "https://www.worldtides.info/api/v2?extremes&days=2&date=today&heights&plot"
            "&key={}&lat={}&lon={}"
        ).format(self._key, self._lat, self._lon)

        try:
            self.data = requests.get(resource, timeout=10).json()
            _LOGGER.debug("Data: %s", self.data)
            _LOGGER.debug("Tide data queried")
        except ValueError as err:
            _LOGGER.error("Error retrieving data from WorldTidesInfo: %s", err.args)
            self.data = None
